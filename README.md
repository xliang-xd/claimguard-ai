# ClaimGuard AI

面向保险文字客服的 Copilot 与 AI 智能质检系统。ClaimGuard AI 是聚焦保险文字服务的 GitHub 演示项目，不处理电话、ASR、说话人分离、OCR、视频或智能外呼。

## 当前版本

当前软件包版本为 `0.6.0`。它保留独立、默认离线的 QA CLI，并将最小 Copilot 的条款检索升级为可核验的交付路径：

```text
Policy Tool -> Evidence Ledger -> Citation Judge -> Runtime Gate
```

![ClaimGuard AI v0.6 架构图](docs/assets/architecture.svg)

Policy Tool 先检索本地知识索引中的候选条款，再以 Qwen Reranking 选择可用证据。选中条款写入当前进程、当前轮的内存 Evidence Ledger。Citation Judge 以严格 Schema 判定草稿是否受这些证据支持；Runtime Gate 会再次校验 verdict 和条款 ID，只有 `supported` 才会交付草稿并保存本进程会话状态。其他情况均 fail closed 为 `human_takeover`。

当前唯一的实时 Handoff 是 `Router -> Policy Agent`。Claims、Complaint、持久 Session、审批、副作用工具和 Web/API 均未实现，也不属于当前运行路径。

## V1 产品

### 客服 Copilot

- 识别保单、保障责任、等待期和免责等条款解释意图。
- 检索并重排相关保险条款。
- 仅在当前 Evidence Ledger 支持引用时交付草稿。
- 在证据不足、引用不支持或运行时核验失败时转人工。

### 智能质检

- 审查已完成文字对话并生成稳定 JSON 报告。
- 运行确定性规则、可选 RAG 依据检索与可选语义质检。
- 保持默认离线行为；只有显式使用需要模型的能力时才会发起网络请求。

## 安全与数据边界

API Key 仅从被忽略的本地 `.env` 或显式进程环境变量读取。OpenAI 托管 tracing 默认关闭。Ledger 不是持久存储，`InMemorySessionStore` 也只支持同一进程内恢复。

审计只保存条款 ID、数量、分数范围、verdict 状态、引用条款 ID 与失败类别等受控元数据。API Key、草稿全文、原始服务响应和审计正文不得进入终端记录、文档、报告或 Git。

## 快速开始

项目要求 Python 3.10 或更高版本。运行默认离线的 QA 演示：

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/claim-amount-dispute.json
```

运行完整离线测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Reranking、Citation Judge 和 Copilot 的真实 smoke 需要本地 Model Studio 配置。它与离线评测分开执行，且输出必须受控：只允许记录退出码、`current_agent`、verdict 状态、引用条款 ID 与是否转人工。缺少 `.env` 或 `DASHSCOPE_API_KEY` 时安全跳过，不读取或打印 `.env` 内容。

## 文档

- [架构](docs/architecture.md)：当前证据链、审计边界与版本范围。
- [Agent 编排](docs/agent-orchestration.md)：固定 Handoff、Runtime Gate 与独立 QA。
- [M6 操作与验证](docs/m6-reranking-citation-judge.md)：Reranking、Ledger、Judge、离线评测和受控 smoke。
- [版本策略](docs/versioning.md)：`v0.6.0` 与下一项 `v0.7.0` 的边界。

## 路线图

![ClaimGuard AI 路线图](docs/assets/roadmap.svg)

`v0.6.0` 是当前已交付的引用核验里程碑；`v0.7.0` 是下一项后续里程碑。后续能力不会被画作或描述为当前可用接口。
