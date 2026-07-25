# KnowFlow Agent 贡献边界

KnowFlow Agent 是 LI Jiale 基于 Hermes Agent 构建的非官方独立扩展项目，不属于 Nous Research。项目固定依赖 Hermes Agent `0.18.2`，上游 commit 为 `9de9c25f620ff7f1ce0fd5457d596052d5159596`；本仓库未复制或修改 Hermes 核心源码。

## 个人开发

- PDF、DOCX、Markdown、TXT 解析、清洗、结构切分、页码/标题保留和增量索引；
- 项目隔离的 SQLite/Chroma 数据生命周期、启动恢复与删除同步；
- Dense、BM25、RRF 混合检索，以及引用 allow-list、拒答与 Prompt 版本管理；
- FastAPI、Streamlit、统一领域契约、JSON 日志、trace ID、错误映射与敏感字段脱敏；
- `knowledge_search`、`knowledge_answer` 薄插件的参数/结果适配；
- GitHub MCP 的只读工具白名单、仓库白名单、超时和失败处理；
- 最多三个 child 的有限业务流程、知识库日报生成和幂等状态记录；
- 56 条评测集、评测程序、pytest、Docker、GitHub Actions 与交付文档。

## 集成工作

- 使用 Chroma、BGE、BM25、SQLite、FastAPI 和 Streamlit 组成应用工程；
- 配置 Hermes 项目插件和远程 GitHub MCP；
- 通过 Hermes `delegate_task` 与 Cron 承载有限子任务和定时触发。

## Hermes 上游已有能力

以下能力属于 Hermes Agent，不能写成个人独立研发成果：

- Agent Loop、Provider 调用与 Prompt/工具 Schema 组装；
- Tool Registry、Function Calling 调度和安全审批；
- Memory、FTS5 Session Search、MCP 客户端；
- Cron 调度器、`delegate_task`、Gateway 和 Plugin 框架。

## 可审计证据

- 5 个功能 Issue、独立分支和对应 PR；
- 51 个 pytest、Ruff、strict mypy 与 GitHub Actions 记录；
- 56 条固定评测数据及 `reports/evaluation/hash-ci.json` 原始结果；
- `UPSTREAM.md`、`THIRD_PARTY_NOTICES.md` 与 MIT License。
