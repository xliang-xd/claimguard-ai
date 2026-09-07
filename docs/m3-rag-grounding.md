# M3：v0.3 RAG 依据能力

`v0.3.0` 为 QA CLI 新增确定性的、可产出证据的保单依据能力。其范围有意保持狭窄：运行时只会为命中的中文知识规则检索条款，并将该条款作为补充证据返回。未使用索引时，现有 QA 命令保持兼容与离线。

## 支持的中文保单规则

| 规则 | 支持的情形 | 预期保单条款 |
| --- | --- | --- |
| `RAG-001` | 涉及免赔额的赔付金额异议 | `12` 免赔额 |
| `RAG-002` | 因等待期被拒赔的就诊 | `18` 等待期 |
| `RAG-003` | 疾病不在保障范围内 | `24` 疾病保障范围 |
| `RAG-004` | 客户询问意外定义 | `31` 意外事故定义 |
| `RAG-005` | 宠物险拒赔需要动态条款引用 | 检索匹配条款 |

规则选择采用确定性的短语匹配。依据证据包含检索到的条款 ID、标题、完整条款文本、来源路径和检索得分。

## 模型与本地索引

v0.3 的 Embedding 边界默认使用阿里云 Model Studio / Qwen `qwen3.7-text-embedding`，维度为 1024。它只在构建索引以及为有依据 QA 运行检索证据时使用。索引是经过验证的 JSON 产物，应置于被忽略的 `.claimguard/` 目录中。它不是源数据；保单变动、Embedding 模型变动或维度变动后都必须重建。

`qwen3-rerank` 被记录为未来选项，但 v0.3 不会调用它。LLM Judge 与 LLM 引用判断同样延后。

## 操作者设置

将 `.env.example` 复制为被忽略的 `.env`，把 `DASHSCOPE_API_KEY` 设置为本地 Model Studio Key，然后从已提交的合成保单 fixture 创建索引：

```bash
cp .env.example .env
# 仅在本地编辑 .env：DASHSCOPE_API_KEY=your-key
PYTHONPATH=src python3 -m claimguard.cli index data/knowledge/petcare-plus-policy-zh.md \
  --output .claimguard/petcare-plus-policy.json
```

针对该本地产物运行有依据的 QA：

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/zh-deductible-dispute.json \
  --index .claimguard/petcare-plus-policy.json
```

进行手动真实 API 发布检查时，在 Key 已存在于 `.env` 或当前进程后运行上述两条命令。进程环境变量优先于 `.env`。检查输出中是否成功创建索引与条款证据，但不要打印、记录或以其他方式暴露 Key。旧命令既不需要索引也不需要 Key：

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/claim-amount-dispute.json
```

## 已知限制

- 覆盖范围限于上述五个有 fixture 支持的中文 RAG 案例。
- 检索使用一个 Embedding 模型和余弦相似度，不含 Reranking。
- 检索证据展示所选条款；它不证明生成回复在法律上完整，也不执行 LLM 引用判断。
- 项目使用合成保单与对话 fixture，而不是生产保险记录。
- 仅 Embedding 索引创建和有依据检索需要网络访问。单元测试使用本地字面向量，不发起远程调用。
