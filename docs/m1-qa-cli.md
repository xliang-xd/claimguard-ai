# M1 QA CLI

M1 为 ClaimGuard AI 引入首个本地 QA 闭环。

## 已实现能力

- 加载已完成文字对话 fixture。
- 加载 V1 规则目录。
- 生成确定性 QA 报告。
- 返回包含对话 ID、场景、得分、结论、证据和建议的 JSON。

## 有意保留的限制

- 尚未接入实时 LLM Judge。
- 尚未接入向量检索或真实 RAG。
- 结论来自 fixture 的 `expected_risks`，以便在加入模型行为前先稳定报告契约。

## 运行

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/claim-amount-dispute.json
```

## 报告字段

- `conversation_id`：被审查对话的 fixture 标识。
- `scenario`：便于人阅读的案例说明。
- `score`：确定性质量得分，当前为 `100 - 10 * finding_count`。
- `findings`：由 fixture 预期风险生成的、有序规则结论列表。
- `evidence`：M1 中用作确定性证据片段的第一条客服回复。
- `recommendation`：占位辅导文本；未来 LLM/RAG 工作会以有条款依据的建议替换它。
