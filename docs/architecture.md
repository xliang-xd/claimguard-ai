# 架构

ClaimGuard AI 当前对外运行能力包括 v0.4 QA 和 v0.5.0 的最小 Copilot。确定性规则始终执行；RAG 依据检索和语义判断是添加到同一份稳定 QA 报告中的可选能力。Copilot 已启用固定的 `Router -> Policy Handoff`，不会改变 QA 报告契约。

## 语义质检（当前）

对于一段已完成对话，`--llm` 会调用一次阿里云 Model Studio 的 Qwen `qwen3.7-plus`，使用严格 JSON Schema、`temperature: 0` 并关闭思考模式。它评估 `SEM-002` 至 `SEM-005`：回答相关性、服务态度不耐烦、投诉承认与安抚，以及无依据的确定性承诺。

只有当返回证据精确等于对话中的一整条客服消息时，报告构建器才会接受一项语义违规。对于已经由确定性匹配产生的规则，它会去重。服务商、传输或契约错误会终止命令，而不会加入未经验证的结论。

未传入 `--llm` 时，语义客户端不会创建，普通 CLI 也不会产生语义网络请求。

## 流程质检（后续）

目标流程规则将结合确定性检查和 LLM 规范化处理。未来工作旨在接受更灵活的表达，同时继续执行身份披露、会话结束等必要服务步骤。

## 知识依据质检（当前）

知识依据规则会解析受支持的中文保单标题，使用 `qwen3.7-text-embedding` 构建并查询本地 JSON 索引，并将检索排名第一的条款附加到结论。已实现的规则是 `RAG-001` 至 `RAG-005`，覆盖免赔额、等待期、保障范围、意外定义和拒赔引用案例。报告将条款 ID、标题、文本、来源路径和检索得分作为补充证据输出。

索引构建和查询期检索被有意分开：

```text
显式索引命令
  保单 Markdown -> 解析器 -> Qwen Embedding -> 被忽略的本地 JSON 索引

带 --index 的 QA 命令
  命中的 RAG 规则 -> 查询 Embedding -> 既有本地索引 -> 条款证据
```

本地索引是位于 `.claimguard/` 下、供操作者使用且被忽略的产物。Embedding 客户端只在创建索引和有依据检索时创建；旧版 QA CLI 仍然完全离线，也不需要 Key。

## Copilot 运行时（当前）

Copilot 采用 OpenAI Agents SDK for Python。v0.5.0 已启用 Agents SDK Runner、Qwen Provider、Router、Policy Agent 和 Policy Tool；模型服务通过独立 Qwen Provider 接入中国大陆地域的 Model Studio。所有推理、Embedding 和 Reranking 模型仍默认使用 Qwen。

```text
Web / CLI
  -> Agents SDK Runner
     -> Qwen Provider
     -> Router
        -> Policy Agent
           -> Policy Tool（检索条款）
```

第一版按单组织内部系统运行；每个运行上下文必须保留 `tenant_id`、`user_id` 和 `session_id`。应用通过 `InMemorySessionStore` 保存同一进程内的多轮状态；持久 Session 与跨进程恢复仍未实现。默认 JSONL 审计路径是 `.claimguard/audit.jsonl`。

SessionStore 的 `exclusive_session` 是可选能力。只提供 `load` 和 `save` 的旧 Store 仍可运行，Runtime 会在当前实例和当前事件循环内按会话串行化；该兼容回退不能协调多个 Runtime 实例或事件循环共享同一 Store 的 `load-run-save` 操作。需要这一并发保证的 Store 必须实现 `exclusive_session`。

OpenAI 托管 tracing 默认关闭；本地结构化审计始终开启，并作为正式路径。审计事件拒绝原始客户消息和凭据字段。API Key 只从被忽略的 `.env` 或进程环境读取，严禁进入异常或任何输出表面（包括标准输出、标准错误、日志、报告和审计），也不得写入 fixture 或 Git；Agent 不直接持有 API Key、数据库连接或其他基础设施凭据。

## 版本边界

- `v0.5.0`：已启用 Agents SDK Runner、Qwen Provider、`Router -> Policy Handoff`、Policy Tool、进程内 Session 和本地审计。
- Claims、Complaint、Compliance Guard 的完整能力、Citation Judge、Reranking、持久化 Session、审批、副作用工具和 Web/API 工作台继续后移。

现有 QA CLI 暂不迁移到 Agents SDK。检索证据只用于定位选中的条款，不构成引用准确性判断。

## 规划目录

```text
data/knowledge/              保单文本与条款 fixture
examples/conversations/      用于演示和测试的示例对话
src/claimguard/              应用软件包
tests/                       自动化检查
```

v0.3 操作说明见 `docs/m3-rag-grounding.md`，v0.4 语义操作契约见 `docs/m4-semantic-qa.md`，v0.5 Copilot 操作说明见 `docs/m5-agents-sdk-foundation.md`。

维护中的 Agent 拓扑、国产模型默认配置和更新策略见 `docs/agent-orchestration.md`。
