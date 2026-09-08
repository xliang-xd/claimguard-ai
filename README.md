# ClaimGuard AI

面向保险文字客服的 Copilot 与 AI 智能质检系统。

ClaimGuard AI 是一个聚焦于保险文字服务的 GitHub 演示项目。不处理电话、ASR、说话人分离、OCR、视频或智能外呼。V1 只关注两类输入：

1. 正由在线客服处理的客户消息。
2. 需要接受质检的已完成文字对话。

## 架构

![ClaimGuard AI 架构图](docs/assets/architecture.svg)

当前对外运行能力仍是 v0.4 QA：确定性 QA、可选的 RAG 依据检索，以及面向已完成中文对话的可选语义质检。只有当操作者显式传入 `--llm` 时，语义裁判才会执行一次；默认 CLI 保持离线。`v0.4.2` 只记录 Copilot 架构设计，没有启用 Copilot 运行代码，也不改变 QA 报告契约。

## V1 产品

### 客服 Copilot

Copilot 工作流在实时聊天中帮助客服回复客户。

- 识别客户意图，例如赔付金额异议、拒赔说明、保单条款查询或投诉。
- 检索相关保险知识。
- 起草清晰、合规且有条款依据的回复。
- 提醒客服避免高风险措辞、无依据承诺和不耐烦表达。

### 智能质检

QA 工作流审查已完成对话。

- 生成质检得分。
- 运行语义、流程和知识依据规则。
- 展示违规规则 ID、风险等级、证据和判定理由。
- 提供有正确保单条款依据的改进回复建议。

## V1 目标规则矩阵

当操作者显式传入 `--llm` 时，`SEM-002` 至 `SEM-005` 生效。确定性规则运行器和 RAG 依据检索无需语义模型调用即可使用。`SEM-001`、流程规范化和引用判断仍处于延后状态。

| 规则 ID | 规则 | 类别 | 风险 | 检测方式 |
| --- | --- | --- | --- | --- |
| SEM-001 | 反诘客户 | 语义 | 极高 | LLM Judge（后续） |
| SEM-002 | 回答未覆盖客户意图 | 语义 | 极高 | Qwen 语义裁判（`--llm`） |
| SEM-003 | 服务态度不耐烦 | 语义 | 极高 | Qwen 语义裁判（`--llm`） |
| SEM-004 | 投诉未被承认或安抚 | 语义 | 极高 | Qwen 语义裁判（`--llm`） |
| SEM-005 | 未获批准的承诺 | 语义 | 极高 | Qwen 语义裁判（`--llm`） |
| PROC-001 | 身份披露不完整 | 流程 | 高 | 规则 + LLM（后续） |
| PROC-002 | 缺少结束语 | 流程 | 低 | 规则 + LLM（后续） |
| RAG-001 | 赔付金额异议：免赔额 | 知识依据 | 中 | 确定性 RAG 证据 |
| RAG-002 | 投保前或等待期内就诊拒赔 | 知识依据 | 中 | 确定性 RAG 证据 |
| RAG-003 | 疾病不在保单保障范围内 | 知识依据 | 中 | 确定性 RAG 证据 |
| RAG-004 | 意外定义说明 | 知识依据 | 中 | 确定性 RAG 证据 |
| RAG-005 | 宠物险拒赔的动态条款引用 | 知识依据 | 高 | 意图 + RAG 证据 + Citation Judge（后续） |

`RAG-005` 是 V1 的重点演示案例，因为它计划在一个场景中展现意图路由、检索、引用准确性和有依据的回答质量。v0.4 仅附加检索到的条款证据；引用准确性仍需要未来的 Citation Judge。

## Copilot 技术方向

Copilot 将采用 OpenAI Agents SDK for Python，编排采用固定的 `Router -> Policy / Claims / Complaint Handoff`：

```text
Router
  -> Policy Agent
  -> Claims Agent
  -> Complaint Agent
```

所有推理、Embedding 和 Reranking 模型仍默认使用 Qwen。OpenAI 托管 tracing 默认关闭，本地结构化审计是正式路径。QA Agent 保持独立，继续审查已完成对话。`v0.5.0` 才会启用最小 `Router -> Policy Handoff`；Claims、Complaint、审批和 Web/API 工作台继续按路线图后移。

## 当前里程碑

当前软件包版本：`0.4.2`。

M2 引入首个确定性规则运行器。QA 结论现在来自对话文本，而非 fixture 中的 `expected_risks` 字段。在 LLM 行为仍处于开发阶段时，该字段继续作为测试预期数据。

`v0.2.1` 是文档补丁，新增 README 架构图和路线图。

`v0.2.2` 是文档补丁，记录维护中的 Agent 编排和国产模型默认配置，详见 `docs/agent-orchestration.md`。

`v0.3.0` 新增确定性的中文保单依据能力：保单解析器和已验证的本地索引、Qwen `qwen3.7-text-embedding` 检索、五条受支持的 RAG 规则、QA 结论中的检索证据，以及兼容旧用法的索引创建与依据质检 CLI 命令。它不包含 LLM Judge、Reranking 或引用准确性判断。

`v0.3.1` 新增被 Git 忽略的项目本地 `.env` 配置回退。显式设置的进程环境变量仍具有更高优先级。

`v0.4.0` 为 `SEM-002` 至 `SEM-005` 新增可选的语义质检。使用 `--llm` 时，一次 Qwen `qwen3.7-plus` 结构化输出请求会评估一段已完成对话。只有当语义结论的证据精确等于该对话中的一整条客服消息时，系统才会输出该结论；服务商或契约错误会返回失败，而不是产生未经验证的结论。

`v0.4.1` 将解释性文档和技术图本地化为中文，不改变已交付功能范围。

`v0.4.2` 冻结 OpenAI Agents SDK Copilot 架构：固定 Router 与 Policy、Claims、Complaint 的 Handoff 边界，保留 Qwen 默认模型、本地 Session 与本地审计，并明确 OpenAI 托管 tracing 默认关闭。此版本仍只运行 v0.4 QA，不包含 Copilot 运行时。

## 仓库结构

```text
docs/                       产品范围与架构说明
data/knowledge/             合成保单 fixture
examples/conversations/     演示对话 fixture
src/claimguard/             Python 软件包
tests/                      自动化测试
```

## 版本管理

发布标签采用 `vX.Y.Z` 格式。

- 小型改动使用 `v0.0.Z` 形式的补丁版本。
- 较大的功能里程碑使用 `v0.Y.0` 形式的次版本。
- `vX.0.0` 主版本只留给真正可交付的演示里程碑。

项目具体规则见 `docs/versioning.md`。

## 快速开始

运行当前 QA CLI 演示：

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/claim-amount-dispute.json
```

为有依据的 QA 创建本地保单知识索引。先复制本地模板，再将 Model Studio API Key 写入 `.env`。该文件会被 Git 忽略：

```bash
cp .env.example .env
# 仅在本地编辑 .env：DASHSCOPE_API_KEY=your-key
PYTHONPATH=src python3 -m claimguard.cli index data/knowledge/petcare-plus-policy-zh.md \
  --output .claimguard/petcare-plus-policy.json
```

使用生成的索引运行 QA：

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/zh-deductible-dispute.json \
  --index .claimguard/petcare-plus-policy.json
```

生成的索引保存在 `.claimguard/petcare-plus-policy.json`。API Key 和生成的索引不会提交。当显式设置时，进程环境变量会覆盖 `.env` 中的同名值。

支持的中文案例、索引生命周期、操作者命令和当前限制见 `docs/m3-rag-grounding.md`。

针对专用中文 fixture 运行语义质检：

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/zh-semantic-qa.json --llm
```

这是一次明确会产生费用的 Model Studio 网络调用。它复用被忽略的本地 `.env` 配置（或显式进程环境变量），因此 API Key 不应出现在命令、fixture 或 Git 历史中。语义裁判要求证据为一整条有来源的客服消息。如果请求或响应无法通过验证，命令会失败，且不会生成语义结论。运行契约和限制见 `docs/m4-semantic-qa.md`。

命令返回 JSON QA 报告，其中包括：

- `conversation_id`：被审查对话 fixture 的 ID。
- `scenario`：演示案例说明。
- `score`：确定性的质检得分。
- `findings`：包含规则 ID、类别、风险等级、证据和建议的规则结论。

运行测试套件：

```bash
python3 -m unittest discover -s tests
```

加载 V1 规则目录：

```python
from claimguard.rules import load_rule_catalog

catalog = load_rule_catalog()
print(catalog.get("RAG-005").name)
```

## 路线图

![ClaimGuard AI 路线图](docs/assets/roadmap.svg)

路线图将小型文档或 fixture 更新放在补丁版本中，而将能力里程碑提升到次版本。
