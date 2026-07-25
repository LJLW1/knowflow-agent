# Atlas 系统架构

## 接口层

服务使用 FastAPI 提供 HTTP API，并通过 Pydantic 契约校验请求与响应。Streamlit 只用于内部演示，不承载核心业务逻辑。

## 数据层

SQLite 保存项目元数据、文档记录和任务历史。Chroma 保存向量及其 `project_id`、`document_id`、`index_version_id` 元数据。所有数据查询必须包含 `project_id`。

## 检索层

稠密检索使用本地 BGE 中文 Embedding。优化方案将 BM25 与向量检索结果通过 RRF 合并，默认返回六个候选 Chunk。

## 任务语义

TaskRun 是单进程内任务，不是持久分布式队列。服务重启后，运行中的任务标记为 `interrupted`，错误码为 `PROCESS_RESTARTED`。
