# 版本管理策略

ClaimGuard AI 使用 `vX.Y.Z` 形式的 Git 发布标签，Python 包元数据遵循不带前导 `v` 的 PEP 440 格式。

## 升级规则

- `v0.0.Z`：小型修复、文档更正、fixture 调整和范围较小的内部改进。
- `v0.Y.0`：较大的功能里程碑、新的面向用户命令、新工作流和有意义的能力升级。
- `vX.0.0`：只用于可交付的主版本，例如可作为完整作品集里程碑分享的完善演示。

## 当前解释

- `v0.5.0` 启用 Qwen Provider、Agents SDK Runner、最小 `Router -> Policy Handoff`、Policy Tool、进程内 Session 和本地审计。
- `v0.6.0` 在该 Copilot 路径后新增 Qwen Reranking、每轮内存 Evidence Ledger、严格 Citation Judge 与 fail-closed Runtime Gate。只有 Ledger 中的条款 ID 支持且 verdict 为 `supported` 时，草稿才可交付和保存会话状态。
- `v0.7.0` 为下一项后续里程碑。Claims、Complaint、持久 Session、审批、副作用工具和 Web/API 没有包含在 `v0.6.0` 内。

## 实务规则

- Python 最低运行版本为 3.10，以满足 `openai-agents>=0.14,<0.15`。
- Git 标签和 GitHub 发布名称采用带前导 `v` 的版本，例如 `v0.6.0`。
- API Key、草稿、原始响应与审计正文不得进入标签说明、提交、发布文档或报告。
- 在具备可用的端到端演示、文档化设置步骤、示例数据、测试和清晰用户工作流之前，不创建 `v1.0.0` 发布。
