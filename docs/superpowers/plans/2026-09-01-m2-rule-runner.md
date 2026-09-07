# M2 确定性规则运行器实施记录

## 目标

以确定性文本规则替代 M1 中由 fixture `expected_risks` 驱动的运行时结论，同时保持 QA 报告和 CLI 契约兼容。

## 交付内容

- 将 V1 规则目录作为规则定义来源。
- 为赔付金额异议的回避回答检测 `SEM-002`。
- 为不耐烦或“结果已定”措辞检测 `SEM-003`。
- 为缺少免赔额/条款说明的赔付异议检测 `RAG-001`。
- 扩充规则运行器、报告和 CLI 的自动化测试。

## 范围与验证

本阶段面向英文演示 fixture，先覆盖核心演示路径；中文 RAG、LLM Judge 与 Citation Judge 仍延后。验证采用：

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/claim-amount-dispute.json
```

该能力对应 `v0.2.0`，其后仅文档改动使用补丁版本。
