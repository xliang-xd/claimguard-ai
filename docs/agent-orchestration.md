# Agent 编排

ClaimGuard AI 保留两条独立工作流：已完成对话的 QA Agent 与实时客服 Copilot。`v0.6.0` 的 Copilot 仍只有固定的 `Router -> Policy Agent` Handoff；本次新增的是 Policy Agent 之后的证据与引用交付门槛，不是新的 Agent 拓扑。

![ClaimGuard AI v0.6 Agent 编排图](assets/agent-orchestration.svg)

## 当前 Copilot 编排

```text
客户消息
  -> Router Agent
  -> Policy Agent
  -> Policy Tool
  -> Evidence Ledger（仅当前进程、当前轮）
  -> Citation Judge
  -> Runtime Gate
  -> draft_ready 或 human_takeover
```

Router 仅将保单解释意图交给 Policy Agent。Policy Tool 对本地索引召回的候选条款进行 Qwen Reranking，按最低重排分数选择条款，并把相同的 `EvidenceRecord` 同时作为工具结果的来源和 Ledger 的唯一证据类型。

Citation Judge 只接收草稿和当前 Ledger 快照。它返回受控 verdict：`supported`、`unsupported` 或 `insufficient_evidence`。Runtime 不信任任何未再次验证的 Judge 输出：没有证据、没有 Judge、无效 verdict、未知条款 ID、非 `supported` 结果或审计失败，都会 fail closed 为 `human_takeover`，不交付草稿，也不推进会话状态。

## Session 与审计

`InMemorySessionStore` 仅为同一进程的后续轮次保存结构化输入状态。Ledger 不写入 Session，并在每轮开始时清空；持久 Session 与跨进程恢复仍未实现。

审计只允许安全元数据：条款 ID、数量、分数范围、verdict 状态、引用 ID 与失败类别。不得写入客户消息、草稿、原始模型响应、Judge 原因正文或凭据。

## 独立 QA Agent

QA Agent 不参与实时 Handoff。它继续提供确定性规则、可选 RAG 依据和仅在 `--llm` 时执行的语义质检，保持既有 QA JSON 报告契约和默认离线行为。

## 已实现与后续

| 范围 | `v0.6.0` 状态 |
| --- | --- |
| `Router -> Policy Agent` | 已实现 |
| Policy Tool、Reranking、Evidence Ledger | 已实现 |
| Citation Judge、Runtime Gate | 已实现且 fail closed |
| Claims、Complaint | 未实现 |
| 持久 Session、审批、副作用工具、Web/API | 未实现 |

`v0.7.0` 是下一项后续里程碑。它不属于当前运行图，也不应被解读为已存在的 Handoff、工具或服务接口。
