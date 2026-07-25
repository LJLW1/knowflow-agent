"""Application factory and the six public API endpoints."""

from __future__ import annotations

import uuid
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from knowflow.api.schemas import QueryRequest, TaskRequest
from knowflow.config import Settings
from knowflow.document.parsers import InvalidDocumentError
from knowflow.document.service import DocumentService
from knowflow.domain.models import TaskStatus
from knowflow.persistence.database import Database
from knowflow.persistence.repositories import KnowledgeRepository
from knowflow.observability import configure_logging
from knowflow.rag.llm import LLMNotConfigured, OpenAICompatibleLLM
from knowflow.rag.service import LLM, RAGService
from knowflow.retrieval.embedding import BGEEmbedding, HashEmbedding
from knowflow.retrieval.chroma import ChromaVectorStore
from knowflow.retrieval.hybrid import HybridRetriever
from knowflow.retrieval.store import InMemoryVectorStore


class Container:
    def __init__(self, settings: Settings, llm: LLM | None) -> None:
        self.settings = settings
        for directory in (settings.upload_path, settings.report_path, settings.chroma_path):
            Path(directory).mkdir(parents=True, exist_ok=True)
        self.database = Database(settings.database_url)
        self.database.initialize()
        self.repository = KnowledgeRepository(self.database)
        embedding = (
            BGEEmbedding(settings.embedding_model)
            if settings.embedding_backend == "bge"
            else HashEmbedding()
        )
        self.vector_store = (
            ChromaVectorStore(settings.chroma_path, embedding)
            if settings.vector_backend == "chroma"
            else InMemoryVectorStore(embedding)
        )
        if settings.vector_backend != "chroma":
            for project_id in self._known_projects():
                self.vector_store.add(self.repository.list_chunks(project_id))
        self.retriever = HybridRetriever(self.vector_store)
        self.documents = DocumentService(self.repository, self.vector_store)
        self.llm = llm or OpenAICompatibleLLM(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
        )
        self.rag = RAGService(
            self.retriever,
            self.llm,
            filename_resolver=self._filename,
        )

    def _known_projects(self) -> list[str]:
        from sqlalchemy import select

        from knowflow.persistence.tables import ProjectRow

        with self.database.session() as session:
            return list(session.scalars(select(ProjectRow.project_id)).all())

    def _filename(self, project_id: str, document_id: str) -> str:
        document = self.repository.get_document(project_id, document_id)
        return document.filename if document else document_id

    def refresh_retriever(self, project_id: str) -> None:
        self.retriever.replace_project_chunks(project_id, self.repository.list_chunks(project_id))


def create_app(settings: Settings | None = None, *, llm: LLM | None = None) -> FastAPI:
    configuration = settings or Settings()
    configure_logging(configuration.log_level)
    container = Container(configuration, llm)
    logger = logging.getLogger("knowflow.api")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        container.repository.interrupt_running_tasks()
        yield

    app = FastAPI(title="KnowFlow Agent API", version="0.1.0", lifespan=lifespan)
    app.state.container = container

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next: Any):
        trace_id = request.headers.get("x-trace-id") or f"tr_{uuid.uuid4().hex}"
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["x-trace-id"] = trace_id
        logger.info(
            "request_completed",
            extra={
                "fields": {
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                }
            },
        )
        return response

    @app.exception_handler(LLMNotConfigured)
    async def llm_error(request: Request, _: LLMNotConfigured) -> JSONResponse:
        return _error(request, "LLM_NOT_CONFIGURED", "未配置可用的大模型。", 503)

    @app.exception_handler(InvalidDocumentError)
    async def document_error(request: Request, exc: InvalidDocumentError) -> JSONResponse:
        return _error(request, str(exc), "文档无法解析。", 400)

    @app.exception_handler(ValueError)
    async def value_error(request: Request, exc: ValueError) -> JSONResponse:
        code = str(exc) if str(exc).isupper() else "INVALID_REQUEST"
        return _error(request, code, "请求参数不合法。", 400)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/api/v1/documents", status_code=201)
    async def upload_document(
        request: Request,
        project_id: str = Form(...),
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        container.repository.create_project(project_id, project_id)
        data = await file.read()
        result = container.documents.ingest(project_id, file.filename or "", data)
        container.refresh_retriever(project_id)
        return {
            "document": result.document.model_dump(mode="json"),
            "chunks_indexed": result.chunks_indexed,
            "skipped": result.skipped,
            "trace_id": request.state.trace_id,
        }

    @app.post("/api/v1/query")
    def query(request: Request, payload: QueryRequest) -> dict[str, Any]:
        result = container.rag.answer(
            payload.project_id,
            payload.question,
            top_k=payload.top_k,
            trace_id=request.state.trace_id,
        )
        return result.model_dump(mode="json")

    @app.post("/internal/v1/search", include_in_schema=False)
    def internal_search(payload: dict[str, Any]) -> dict[str, Any]:
        project_id = str(payload.get("project_id", ""))
        query_text = str(payload.get("query", ""))
        top_k = int(payload.get("top_k", 6))
        if not project_id or not query_text:
            raise ValueError("INVALID_REQUEST")
        hits = container.retriever.search(project_id, query_text, top_k=top_k)
        return {"hits": [hit.model_dump(mode="json") for hit in hits]}

    @app.post("/api/v1/tasks", status_code=202)
    def create_task(request: Request, payload: TaskRequest) -> dict[str, Any]:
        container.repository.create_project(payload.project_id, payload.project_id)
        task_id = f"task_{uuid.uuid4().hex}"
        task = container.repository.create_task(
            task_id=task_id,
            project_id=payload.project_id,
            status=TaskStatus.PENDING,
            request=payload.model_dump(mode="json"),
            trace_id=request.state.trace_id,
        )
        return task.model_dump(mode="json")

    @app.get("/api/v1/tasks/{task_id}")
    def get_task(task_id: str, project_id: str) -> Any:
        task = container.repository.get_task(project_id, task_id)
        if task is None:
            return JSONResponse(status_code=404, content={"error": {"code": "TASK_NOT_FOUND"}})
        return task.model_dump(mode="json")

    @app.post("/api/v1/evaluations/run", status_code=202)
    def run_evaluation(request: Request) -> dict[str, str]:
        return {"status": "accepted", "run_id": f"eval_{uuid.uuid4().hex}", "trace_id": request.state.trace_id}

    return app


def _error(request: Request, code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "trace_id": request.state.trace_id}},
    )


def run() -> None:
    uvicorn.run("knowflow.api.app:create_app", factory=True, host="0.0.0.0", port=8000)
