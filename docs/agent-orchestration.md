# Agent 编排

ClaimGuard AI 维护两条独立产品工作流：用于完成对话的 QA Agent，以及面向实时客服的 Copilot。v0.5.0 已启用 Copilot 的最小 `Router -> Policy Handoff`；两条工作流仍相互独立。

## 当前 v0.4 QA 工作流

```text
对话
  -> 确定性规则 + 可选 RAG 检索
  -> （仅 --llm）语义裁判
  -> 证据验证器 + 去重器
  -> QA JSON 报告
```

确定性规则运行器始终执行。只有提供本地索引时，可选 RAG 才会贡献检索到的条款证据。`--llm` 会为已完成对话创建一个 Qwen 语义裁判；否则不会存在语义模型客户端或请求。验证器只接受精确等于对话中一整条客服消息的语义证据，去重器会保留同一规则 ID 已有的确定性结果。

索引构建是独立的显式操作：

```text
保单 Markdown -> 保单解析器 -> Qwen Embedding -> 被忽略的本地知识索引
```

它不属于默认 QA 命令。只有操作者传入 `--index` 时，查询期 RAG 才会读取既有索引。

![ClaimGuard AI Agent 编排图](assets/agent-orchestration.svg)

## 产品 Agent

### QA Agent（当前）

已实现的 QA Agent 审查已完成对话，并产出稳定的 JSON 报告，其中包含得分、规则结论、证据、建议、可选的检索条款，以及可选的语义 `reasoning`、`confidence` 和 `judge` 字段。

其生效的语义范围有意保持狭窄：`SEM-002` 至 `SEM-005` 分别覆盖回答相关性、服务态度不耐烦、投诉承认与安抚、以及无依据承诺。模型错误不会产生未经验证的语义结论。

### Copilot Agent（当前最小范围）

Copilot 采用 OpenAI Agents SDK for Python，Router 只负责识别主要意图，并在固定允许图中执行已启用的 Handoff：

```text
Router -> Policy Agent
```

Policy Agent 在回答前必须调用 Policy Tool 检索条款；证据不足时返回 `human_takeover`，证据充分时才返回以“客服草稿：”开头的 `draft_ready`。Claims 和 Complaint 仍未创建为可 Handoff 的运行 Agent；Compliance Guard 的完整能力、审批和副作用工具也仍未启用。QA Agent 不参与实时 Handoff，继续独立运行现有确定性规则、RAG 和可选语义质检。

`InMemorySessionStore` 只支持同一进程内多轮恢复，持久 Session 留待后续里程碑。默认 JSONL 审计路径是 `.claimguard/audit.jsonl`；审计事件拒绝原始客户消息和凭据。

## 国产模型默认配置

面向成本与合规敏感的保险服务场景，ClaimGuard AI 默认使用阿里云 Model Studio / Qwen。配置 API 访问时，目标部署区域为中国大陆，例如 `cn-beijing`。

| 能力 | 默认模型 | `v0.5.0` 状态 |
| --- | --- | --- |
| 语义裁判 | `qwen3.7-plus` | 仅传入 `--llm` 时生效 |
| Embedding | `qwen3.7-text-embedding` | 用于索引创建和 `--index` 检索 |
| Copilot Router | `qwen3.8-flash` | 已启用；仅转交 Policy |
| Policy Agent | `qwen3.7-plus` | 已启用；必须先检索条款 |
| Claims Agent | `qwen3.7-plus` | 延后 |
| Complaint Agent | `qwen3.7-plus` | 延后 |
| Citation Judge | `qwen3.7-plus` | 延后 |
| 疑难案例裁判 | `qwen3.8-max` | 延后 |
| Reranking | `qwen3-rerank` | 延后 |

语义请求使用严格 JSON Schema、`temperature: 0` 并关闭思考模式。本地 `CLAIMGUARD_SEMANTIC_MODEL` 设置可覆盖语义模型。API Key 只从被忽略的 `.env` 或显式进程环境变量读取，严禁进入异常或任何输出表面（包括标准输出、标准错误、日志、报告和审计），也不得写入 fixture 或 Git。

## 运行与审计边界

Agents SDK 负责 Agent、Handoff 和 Runner，Qwen Provider 隔离 Model Studio 的 base URL、认证和模型映射。第一版按单组织内部系统运行，但每个运行上下文必须保留 `tenant_id`、`user_id` 和 `session_id`。默认中国大陆兼容 endpoint 是 `https://dashscope.aliyuncs.com/compatible-mode/v1`，可用 `CLAIMGUARD_DASHSCOPE_BASE_URL` 覆盖。OpenAI 托管 tracing 由 `CLAIMGUARD_OPENAI_TRACING_ENABLED` 控制，未设置时保持关闭；本地 Session 和结构化审计是正式路径。

Citation Judge、Reranking、Claims、Complaint、完整 Compliance Guard、持久化存储和 Web/API 工作台被有意延后。RAG 检索证据用于识别选中的条款，并不是引用准确性结论。

## 设计原则

- 实时 Copilot 与事后 QA 保持独立。
- 专业 Agent 只访问其职责所需的工具与数据。
- 判断与报告优先采用结构化 JSON 输出。
- 让证据可追溯：确定性匹配、完整语义引文和检索条款元数据都保留在报告中。
- 保持确定性规则、语义判断、RAG 和 fixture 可独立测试。
- 默认使用中国大陆服务商以兼顾成本和合规；在实现前记录服务商或模型变更。

## 更新策略

当产品 Agent 拓扑、默认模型、报告契约、RAG 证据格式、本地数据假设，或延后/生效边界发生变化时，同时更新本文档和编排图。
