# KnowFlow 有限子智能体流程

复杂知识任务最多委派三个 child：

1. `knowledge_retrieval`：调用 `knowledge_search` 收集内部文档证据；
2. `github_collection`：仅调用白名单内的只读 GitHub MCP 工具，且仓库必须为 `LJLW1/knowflow-agent`；
3. `citation_validation`：检查最终引用是否来自本轮实际检索 Chunk。

主智能体负责综合。任一 child 超时或失败时保留成功证据，将 Task 标记为 `partial`，不得用模型猜测填补失败结果。
