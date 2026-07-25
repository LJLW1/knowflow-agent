# Atlas API 约定

## 文档接口

`POST /api/v1/documents` 接收项目 ID 和一个 PDF、DOCX、Markdown 或 TXT 文件。相同项目内内容哈希相同的文档会跳过重复索引。

## 问答接口

`POST /api/v1/query` 接收 `project_id`、`question` 和可选的 `top_k`。回答中的引用必须来自本次实际检索并送入模型的 Chunk。

## 任务接口

`POST /api/v1/tasks` 创建进程内任务。`GET /api/v1/tasks/{task_id}` 查询状态时还必须传入 `project_id`，以避免跨项目读取。

## 健康检查

`GET /healthz` 返回服务状态和版本，可供 Docker healthcheck 使用。

## 错误响应

未配置云模型时，问答接口返回 `LLM_NOT_CONFIGURED`。每个错误响应包含稳定错误码和 trace ID。
