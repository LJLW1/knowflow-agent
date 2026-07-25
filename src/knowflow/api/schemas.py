"""HTTP request and response schemas."""

from pydantic import BaseModel, Field

from knowflow.domain.models import AnswerResult


class QueryRequest(BaseModel):
    project_id: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=6, ge=1, le=20)


class QueryResponse(AnswerResult):
    pass


class TaskRequest(BaseModel):
    project_id: str = Field(min_length=1)
    mode: str = "knowledge_report"
    input: dict[str, object] = Field(default_factory=dict)
