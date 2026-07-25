# 已知问题与后续方向

- 当前 TaskRun 由进程内 `BackgroundTasks` 执行，重启后把遗留 `pending/running` 任务标记为 `interrupted`，不保证恢复执行。
- SQLite 与 Chroma 不具备跨存储事务；索引前持久化 `indexing` 标记，异常时补偿，启动时按 SQLite 中的旧 Chunk 恢复。若恢复本身持续失败，服务启动会失败并需要人工排查。
- 尚无云模型 Key，回答忠实度、幻觉率、工具选择准确率、完整任务完成率、Token 成本与端到端延迟待测量。
- 本机 BGE 模型首次下载受当前网络速度影响；CI 的 HashEmbedding 结果只验证流程，不作为语义质量结论。
- Docker Desktop 尚未启动，因此本机 Docker build、healthcheck 和重启持久化验收待执行；镜像在构建阶段缓存 BGE 权重，CI 已配置构建后的容器健康检查。
- 没有 OCR、复杂表格理解、多租户 RBAC/SSO、分布式任务队列或 Kubernetes。
- 后续优先校准拒答阈值、增加 reranker 与 badcase 页面，再考虑 PostgreSQL。
