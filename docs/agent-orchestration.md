# Agent 编排

ClaimGuard AI 保持紧凑的 Agent 拓扑：一个已实现、用于已完成对话的 QA 工作流，以及一个面向实时客服的未来 Copilot 工作流。专用能力保持为工作流节点，而不是面向产品的独立 Agent。

## 当前 v0.4.0 QA 工作流

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

### Copilot Agent（延后）

未来的 Copilot Agent 将在实时聊天中协助客服。计划输出客户意图、推荐条款、建议回复和风险提示。它尚未在 `v0.4.0` 中实现。

## 国产模型默认配置

面向成本与合规敏感的保险服务场景，ClaimGuard AI 默认使用阿里云 Model Studio / Qwen。配置 API 访问时，目标部署区域为中国大陆，例如 `cn-beijing`。

| 能力 | 默认模型 | v0.4.0 状态 |
| --- | --- | --- |
| 语义裁判 | `qwen3.7-plus` | 仅传入 `--llm` 时生效 |
| Embedding | `qwen3.7-text-embedding` | 用于索引创建和 `--index` 检索 |
| 意图 Router | `qwen3.8-flash` | 延后 |
| 规则选择器 | `qwen3.8-flash` | 延后 |
| Citation Judge | `qwen3.7-plus` | 延后 |
| 风险 Guard | `qwen3.7-plus` | 随 Copilot 延后 |
| 回复生成器 | `qwen3.7-plus` | 随 Copilot 延后 |
| 疑难案例裁判 | `qwen3.8-max` | 延后 |
| Reranking | `qwen3-rerank` | 延后 |

语义请求使用严格 JSON Schema、`temperature: 0` 并关闭思考模式。本地 `CLAIMGUARD_SEMANTIC_MODEL` 设置可覆盖语义模型。配置保存在被忽略的 `.env` 或显式进程环境变量中；凭据从不作为报告数据或仓库内容保存。

## 延后拓扑

Citation Judge、Reranking、Copilot 生成、持久化存储和 Web/API 端点被有意延后。RAG 检索证据用于识别选中的条款，并不是引用准确性结论。v0.4 图中将它们展示为未来扩展，而非当前运行时组件。

## 设计原则

- 对外产品架构保持两个 Agent。
- 除非需要独立状态、策略或所有权，否则专用步骤保持为工作流节点。
- 判断与报告优先采用结构化 JSON 输出。
- 让证据可追溯：确定性匹配、完整语义引文和检索条款元数据都保留在报告中。
- 保持确定性规则、语义判断、RAG 和 fixture 可独立测试。
- 默认使用中国大陆服务商以兼顾成本和合规；在实现前记录服务商或模型变更。

## 更新策略

当产品 Agent 拓扑、默认模型、报告契约、RAG 证据格式、本地数据假设，或延后/生效边界发生变化时，同时更新本文档和编排图。
