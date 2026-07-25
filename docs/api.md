# API 使用说明

启动后访问 `http://localhost:8000/docs` 查看 Swagger UI。

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/v1/documents` | multipart 上传与增量索引 |
| POST | `/api/v1/query` | 检索并生成带引用回答 |
| POST | `/api/v1/tasks` | 创建进程内知识库日报任务 |
| GET | `/api/v1/tasks/{task_id}?project_id=...` | 查询项目内任务 |
| POST | `/api/v1/evaluations/run` | 同步执行本地检索评测并持久化结果 |
| GET | `/healthz` | 健康检查 |

## 示例

```bash
curl -F project_id=demo -F file=@demo_corpus/architecture.md \
  http://localhost:8000/api/v1/documents

curl -H 'Content-Type: application/json' \
  -d '{"project_id":"demo","question":"TaskRun 重启后是什么状态？"}' \
  http://localhost:8000/api/v1/query
```

未配置 `KNOWFLOW_OPENAI_API_KEY` 和 `KNOWFLOW_OPENAI_MODEL` 时，问答接口返回 HTTP 503 与 `LLM_NOT_CONFIGURED`；检索、上传和测试不受影响。

Hermes 插件使用未出现在 OpenAPI 中的 `/internal/v1/search`。该端点要求
`X-KnowFlow-Internal-Token` 与 `KNOWFLOW_INTERNAL_API_TOKEN` 完全匹配；
未配置返回 503，令牌错误返回 401。它只用于同机服务调用，不替代面向公网的完整身份系统。
