# M6：Reranking、Citation Judge 与 Runtime Gate

`v0.6.0` 将客服 Copilot 的条款检索升级为可核验的交付链路。它已经实现 Reranking、Evidence Ledger、Citation Judge 和 Runtime Gate；这四项共同决定一份草稿能否离开运行时。

## 已交付能力

1. Policy Tool 对本地索引召回的候选条款调用 Qwen Reranking，默认模型为 `qwen3-rerank`，并按重排分数筛选条款。
2. 选中的条款以 `EvidenceRecord` 写入 Evidence Ledger。每条记录包含条款 ID、标题、来源路径、召回分数和重排分数。
3. Citation Judge 使用严格 JSON Schema 判断草稿是否受当前证据支持，输出 `supported`、`unsupported` 或 `insufficient_evidence`。
4. Runtime Gate 再次验证 verdict 的状态/原因代码配对、引用类型、`supported` 所需的非空引用，以及引用条款 ID 是否都来自当前 Ledger。

当前主链为：

```text
Policy Tool -> Evidence Ledger -> Citation Judge -> Runtime Gate
```

只有 `supported` verdict 且引用 ID 全部存在于本轮 Ledger 时，Runtime 才会记录完成状态、保存本进程会话状态并交付 `draft_ready`。没有证据、Judge 不可用、Judge 出错、结构无效、引用未知、非 `supported` verdict 或完成审计失败时，均返回空草稿的 `human_takeover`，不推进会话状态。

## 生命周期与安全

Evidence Ledger 是当前 Copilot 进程内、当前轮的临时内存。Runtime 在每轮开始时清空 Ledger；它不会作为持久 Session、长期证据库或跨进程恢复机制。

本地审计只允许条款 ID、条款数量、分数范围、verdict 状态、引用条款 ID 与失败类别。正常 Copilot CLI 的 JSON 输出可包含客服草稿，且不改变这一既有契约。只有受控真实 smoke 的持久记录、报告和受控摘要不得保存或打印 API Key、草稿全文、原始模型响应或审计正文。

离线评测与真实 smoke 是不同的验证层：前者使用合成中文宠物险 fixture，覆盖 `supported`、`incomplete`、`wrong_clause`、`no_evidence` 四类，不发起网络请求；后者仅在本地配置和网络可用时受控执行。

## 离线验证

```bash
git diff --check
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m claimguard.cli examples/conversations/claim-amount-dispute.json
```

## 受控真实 smoke

真实 smoke 需要本地被忽略的 `.env` 或显式 `DASHSCOPE_API_KEY`，并会访问 Model Studio。正常 CLI 的 JSON 输出可能包含草稿，因此采集流程必须受控且不改变 CLI：

1. 在工作树外创建临时目录，将 CLI 的标准输出、标准错误和 `--audit` 文件都定向到该目录，绝不把原文显示到终端或写入版本库。
2. 采集器仅在内存中读取临时 JSON 与审计记录，只提取退出码、`current_agent`、verdict 状态、引用条款 ID 和是否转人工。
3. 持久报告只写入这五类受控字段；删除临时目录，不保存草稿全文、原始响应、审计正文或任何凭据。

若本地配置、Key 或网络不可用，应记录“安全跳过”，而不是尝试读取或打印 `.env` 内容。

## 当前边界与下一项

`v0.6.0` 不包含 Claims、Complaint、持久 Session、审批、副作用工具或 Web/API。`v0.7.0` 是下一项后续里程碑；这些能力不得被解读为当前的 Agent、工具、接口或运行时路径。
