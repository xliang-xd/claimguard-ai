# OpenAI Agents SDK Copilot 架构设计

日期：2026-09-07  
目标版本：`v0.5.0` 至 `v1.0.0`  
当前基线：`v0.4.1`

## 1. 背景

ClaimGuard AI 当前包含确定性 QA、可选 RAG 依据检索和可选 Qwen 语义质检。后续 Copilot 将面向企业文字客服场景，必须支持多工具调用、跨轮会话状态、专业 Agent Handoff、人工审批、审计和故障恢复。

Copilot 编排采用 OpenAI Agents SDK。所有推理与 Embedding 模型仍默认使用中国大陆地域的 Qwen 服务；SDK 负责 Agent 运行时能力，不改变国产模型与数据合规策略。

## 2. 目标

- 通过 OpenAI Agents SDK 实现可测试的 Handoff、多工具调用、guardrails、interruptions 和 RunState 恢复。
- 对外提供实时 Copilot 与事后 QA 两条独立产品工作流。
- 让专业 Agent 只访问其职责所需的工具和数据。
- 所有客户回复先形成草稿，并由客服确认后发送。
- 所有副作用操作具备权限校验、人工审批、幂等保护和审计记录。
- 默认关闭 OpenAI 托管 tracing，使用本地结构化审计。
- 第一版按单组织内部系统运行，但数据结构保留多租户扩展字段。

## 3. 非目标

- 不实现电话、ASR、Speaker Diarization、视频或智能外呼。
- 不允许 Agent 自行批准、拒绝或修改理赔决定。
- 不在第一版实现组织注册、套餐计费或租户管理后台。
- 不把确定性规则、检索或权限逻辑迁移进 Prompt。
- 不让 Agent 直接持有数据库连接、API Key 或其他基础设施凭据。

## 4. 核心技术决策

### 4.1 编排框架

使用 OpenAI Agents SDK for Python 作为 Copilot 的运行时框架，使用以下原生概念：

- `Agent`：Router 和专业 Agent。
- `handoffs`：在固定允许图中转交会话控制权。
- function tools：连接内部领域服务。
- guardrails：执行输入、输出和工具边界校验。
- `interruptions` 与 RunState：暂停并恢复需要人工审批的工具调用。
- `last_agent`：在后续轮次中恢复当前专业 Agent。

现有 QA CLI 暂不迁移到 SDK。它继续作为稳定的离线工作流，并逐步把 RAG、Citation Judge 和语义质检暴露为 Copilot 可复用的领域能力。

### 4.2 模型服务

通过 `QwenModelProvider` 将 Agents SDK 接入阿里云 Model Studio 的 OpenAI-compatible Responses API。默认使用中国大陆地域的 workspace-specific endpoint。

| 能力 | 默认模型 | 选择原因 |
| --- | --- | --- |
| Router | `qwen3.8-flash` | 延迟和成本较低，只承担意图分流 |
| Policy Agent | `qwen3.7-plus` | 需要稳定理解复杂条款和上下文 |
| Claims Agent | `qwen3.7-plus` | 需要生成有依据的金额与拒赔解释 |
| Complaint Agent | `qwen3.7-plus` | 需要识别情绪、安抚并判断升级条件 |
| Citation Judge | `qwen3.7-plus` | 需要判断条款是否真实支持回复 |
| 疑难案例评审 | `qwen3.8-max` | 仅在评测证明有必要时升级使用 |
| Embedding | `qwen3.7-text-embedding` | 保持现有索引兼容性 |
| Reranking | `qwen3-rerank` | 提升候选条款排序质量 |

`QwenModelProvider` 必须隔离 base URL、认证、模型映射和兼容性差异。运行时不直接依赖 Model Studio 的非通用响应字段。

### 4.3 数据与 tracing

- 模型请求固定中国大陆地域。
- API Key 仅从被忽略的 `.env` 或进程环境读取。
- OpenAI 托管 tracing 默认关闭，演示环境必须显式开启。
- 本地审计始终开启，但敏感字段按规则脱敏。
- 应用优先保存本地消息历史，不依赖服务商长期保存会话。
- 第一版使用 SQLite，通过 repository interface 隔离；后续增加 PostgreSQL 适配。

## 5. Agent 拓扑

```text
Copilot Router Agent
  ├─ handoff -> Policy Agent
  ├─ handoff -> Claims Agent
  └─ handoff -> Complaint Agent

Compliance Guard
  └─ 横跨 Router、专业 Agent、工具调用和最终回复

QA Agent
  └─ 会话结束后独立运行，复用规则、RAG 和 Citation Judge
```

### 5.1 Router Agent

Router 只负责识别主要意图并选择专业 Agent，不回答复杂保险问题。它使用最少的客户上下文，不访问理赔写入工具。

### 5.2 Policy Agent

负责保障范围、除外责任、等待期、免赔额和保险条款解释。只能访问保单与知识检索类只读工具。

### 5.3 Claims Agent

负责理赔状态、赔付金额拆解、拒赔原因和补充材料说明。可以读取案件数据并生成解释，但不能改变理赔结论。

### 5.4 Complaint Agent

负责明显不满、投诉、安抚和人工升级。可准备投诉或升级操作，但副作用工具必须经过审批。

### 5.5 QA Agent

QA Agent 不参与实时 Handoff。会话结束后，它运行现有确定性规则、RAG、语义质检和未来 Citation Judge，并产生稳定 QA 报告。

## 6. Handoff 规则

固定允许图如下：

```text
Router -> Policy
Router -> Claims
Router -> Complaint
Policy -> Complaint
Claims -> Complaint
Policy -> Router
Claims -> Router
Complaint -> Router
```

- 专业 Agent 不得直接在 Policy 与 Claims 之间相互转交。
- 当客户意图发生实质变化时，专业 Agent 返回 Router 重新分流。
- 当 Policy 或 Claims 检测到明显投诉时，可直接 Handoff 到 Complaint。
- 单个用户轮次最多允许两次 Handoff。
- 超过限制、出现循环或无法可靠分流时，停止 Agent 执行并转人工。

## 7. 工具边界

### 7.1 只读工具

- `search_policy_clauses`
- `get_policy_summary`
- `get_claim_status`
- `get_claim_breakdown`
- `get_customer_context`

### 7.2 分析工具

- `calculate_claim_explanation`
- `validate_citation`
- `assess_response_risk`
- `draft_customer_reply`

### 7.3 副作用工具

- `create_complaint`
- `add_case_note`
- `request_supervisor_review`
- `send_customer_reply`

所有工具使用 typed schema，并统一返回：

```json
{
  "status": "success | denied | retryable_error | fatal_error",
  "data": {},
  "evidence": [],
  "error_code": null,
  "retryable": false,
  "audit_id": "audit_xxx"
}
```

工具上下文由应用注入 `tenant_id`、`user_id`、角色、会话和案件标识。工具内部必须重新校验权限和资源归属，不能依赖 Agent 自报身份。

## 8. 审批策略

- 只读查询和草稿生成无需审批。
- `send_customer_reply` 始终需要当前客服确认。
- 创建投诉、写入案件备注和请求主管升级需要审批。
- 副作用工具必须接收 `idempotency_key`。
- 审批记录包含调用工具、参数摘要、申请人、审批人、决定、时间和审计 ID。
- 审批拒绝后，Agent 只能解释未执行原因或准备替代草稿，不能绕过审批调用其他等价工具。
- 审批超时保持暂停，不自动批准。

当工具需要审批时：

```text
Runner 产生 interruption
  -> 保存 RunState 和待审批操作
  -> 前端显示可审阅参数与影响
  -> 客服或主管批准/拒绝
  -> 从同一 RunState 恢复
  -> 幂等执行或记录拒绝
```

## 9. 状态模型

### 9.1 ConversationState

- `tenant_id`
- `session_id`
- `customer_id`
- `case_id`
- `current_agent`
- 消息历史
- 已取得的业务上下文摘要
- 数据最小化与脱敏标记

### 9.2 RunState

- Agents SDK 可恢复状态
- `last_agent`
- Handoff 次数与路径
- 待审批 interruptions
- 最近一次安全重试信息
- 运行状态：`running`、`waiting_approval`、`completed`、`failed`、`human_takeover`

### 9.3 AuditEvent

- Agent 与模型标识
- 输入输出摘要及脱敏状态
- Handoff 来源与目标
- 工具名称、参数摘要、结果和耗时
- guardrail 结果
- 审批决定
- 错误与降级路径
- trace、run、session 和 tenant 关联 ID

## 10. Guardrails

### 10.1 Input guardrail

- 检测 Prompt injection 和要求绕过规则的内容。
- 拒绝越权查询其他客户或案件。
- 识别并减少传入模型的不必要敏感信息。

### 10.2 Tool guardrail

- 校验角色、租户、资源归属、参数和案件状态。
- 检查副作用工具是否具有有效审批。
- 在执行前创建审计事件，并在执行后记录结果。

### 10.3 Output guardrail

- 验证引用条款是否支持结论。
- 阻止无依据承诺、错误理赔结论和不合规措辞。
- 检查敏感信息泄漏。
- 保证最终输出是草稿，而不是已发送状态。

## 11. 故障与降级

- Router 失败时保留会话并转人工。
- 专业 Agent 或模型请求失败时安全重试一次，再失败则转人工。
- RAG 没有可靠依据时标记依据不足，不生成确定性解释。
- Citation Judge 不通过时禁止发送回复。
- 只读工具可以按相同参数重试。
- 副作用工具重试前必须查询幂等执行结果。
- Handoff 超限或循环时进入 `human_takeover`。
- Model Studio 不可用时，Copilot 降级为确定性模板辅助；既有离线 QA 保持可用。
- 任一 guardrail 或审批组件不可用时，敏感操作失败关闭。

## 12. 测试策略

### 12.1 单元测试

覆盖工具 schema、权限、租户隔离、guardrails、状态转换、幂等和错误映射。

### 12.2 SDK 契约测试

使用假模型和假工具验证：

- Router 正确 Handoff。
- `last_agent` 在后续轮次继续负责。
- interruption 保存可恢复 RunState。
- 批准后副作用只执行一次。
- 拒绝后不执行副作用。
- Handoff 次数和允许图生效。

### 12.3 Qwen 兼容测试

使用受控测试账号验证 Model Studio Responses API 的：

- function calling
- 结构化输出
- 多轮输入
- Handoff 所需的工具调用循环
- 超时、限流和错误响应

兼容测试产生费用，不进入默认离线测试集。

### 12.4 场景评测

覆盖理赔金额异议、等待期拒赔、非保障疾病、投诉升级、诱导承诺、Prompt injection、越权查询、审批拒绝、状态恢复和工具重复执行。

## 13. 版本路线

| 版本 | 里程碑 |
| --- | --- |
| `v0.4.2` | 记录 Agents SDK、Handoff、Qwen provider、本地状态与审批架构 |
| `v0.5.0` | Agents SDK 运行时、Qwen provider、本地 tracing、Session 接口和最小 Router -> Policy Handoff |
| `v0.6.0` | Reranking、Citation Judge 和检索评测集 |
| `v0.7.0` | 完整 Policy、Claims、Complaint Handoff 与只读 Copilot |
| `v0.8.0` | 副作用工具、人工审批、RunState 恢复、角色权限和 Web 工作台 |
| `v0.9.0` | PostgreSQL、批量 QA、审计视图、降级演练和企业评测报告 |
| `v1.0.0` | 可交付的企业级 Copilot + QA Demo |

## 14. 外部兼容性依据

- OpenAI Agents SDK Models and providers：<https://developers.openai.com/api/docs/guides/agents/models>
- OpenAI Agents SDK Results and state：<https://developers.openai.com/api/docs/guides/agents/results>
- OpenAI Agents SDK Guardrails and human review：<https://developers.openai.com/api/docs/guides/agents/guardrails-approvals>
- OpenAI Agents SDK Integrations and observability：<https://developers.openai.com/api/docs/guides/agents/integrations-observability>
- Model Studio OpenAI-compatible Responses API：<https://help.aliyun.com/en/model-studio/qwen-api-via-openai-responses>

这些文档只证明框架与服务商的公开能力边界。实际实现仍必须通过本项目的 SDK 契约测试和 Qwen 兼容测试。
