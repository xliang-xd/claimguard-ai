# 架构

ClaimGuard AI `v0.6.0` 由独立的离线 QA 与受控客服 Copilot 组成。默认 QA CLI 不读取 Key、不发起网络请求；Copilot 使用 OpenAI Agents SDK for Python 和 Qwen Provider，但其草稿交付现在必须通过引用核验的运行时硬门槛。

![ClaimGuard AI v0.6 架构图](assets/architecture.svg)

## 当前 Copilot 证据链

当前唯一的实时 Handoff 是 `Router -> Policy Agent`。Policy Agent 只能使用 Policy Tool；Router、Claims 或 Complaint 之间不存在其他可运行 Handoff。

```text
Policy Tool
  -> 检索候选条款
  -> Qwen Reranking
  -> 选中条款写入 Evidence Ledger
  -> Citation Judge
  -> Runtime Gate
  -> supported 时才交付草稿并保存本进程会话状态
```

Policy Tool 先从本地知识索引召回候选条款，再调用默认 `qwen3-rerank` 重排。仅达到最小重排分数的选中条款会作为 `EvidenceRecord` 写入 Ledger；记录包含条款 ID、标题、来源、召回分数和重排分数。

`EvidenceLedger` 只在当前 Copilot 进程内存中存在。Runtime 在每一轮启动时清空它，因而上一轮证据不能用于当前轮引用核验，也不会被作为持久化存储或跨进程 Session 使用。

Citation Judge 使用严格 JSON Schema 返回 `supported`、`unsupported` 或 `insufficient_evidence`。`supported` 必须引用本轮 Ledger 内至少一个条款 ID；其他状态不得含引用。Runtime 会再次校验状态与原因代码的配对、引用形状和 Ledger 成员资格。仅通过全部检查的 `supported` 结果才会写入完成审计、保存会话状态并交付 `draft_ready`；其余路径一律返回空草稿的 `human_takeover`。

## 审计与安全边界

本地结构化审计只保存受控元数据。Policy 搜索记录条款 ID、数量和重排分数范围；引用门槛记录 verdict 状态、引用条款 ID 和失败类别。审计、报告、文档与命令输出流程不得保存 API Key、草稿全文、原始服务响应或审计正文。

`DASHSCOPE_API_KEY` 仅来自被忽略的本地 `.env` 或显式进程环境变量。OpenAI 托管 tracing 默认关闭。`InMemorySessionStore` 仅支持同一进程内的恢复；持久 Session 未实现。

## 独立 QA 路径

已完成对话的 QA 保持独立：确定性规则始终执行，RAG 检索和 `--llm` 语义质检均为可选能力。它们不进入实时 Copilot Handoff，也不绕过 Citation Judge 的 Runtime Gate。

## 版本边界

- `v0.6.0`：已实现 Reranking、内存 Evidence Ledger、严格 Citation Judge，以及 fail-closed 的 Runtime Gate。
- `v0.7.0`：下一项后续里程碑；当前版本不交付 Claims、Complaint、持久 Session、审批、副作用工具或 Web/API。

完整操作与验证契约见 [M6 文档](m6-reranking-citation-judge.md)。
