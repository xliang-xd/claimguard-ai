# README 图示

本文档记录截至 `v0.4.2` 更新的技术图。`v0.4.2` 增加已批准的 Agents SDK Copilot 设计，但不改变当前 v0.4 QA 的运行行为。

## 资源

- `docs/assets/architecture.svg`：保留索引构建与当前 QA 路径，并以虚线展示未来的 `Web/CLI -> Agents SDK Runner -> Qwen Provider` 以及本地 Session / Audit 边界。
- `docs/assets/architecture.png`：用于视觉检查的渲染预览。
- `docs/assets/roadmap.svg`：从当前 `v0.4.2` 架构准备到 `v1.0.0` 企业级演示的版本路线图，`v0.5.0` Agents SDK 基础标记为下一项。
- `docs/assets/roadmap.png`：用于视觉检查的渲染预览。
- `docs/assets/agent-orchestration.svg`：展示 `Router -> Policy / Claims / Complaint Handoff`、横跨所有 Copilot Agent 的 Compliance Guard，以及独立的 QA Agent。
- `docs/assets/agent-orchestration.png`：用于视觉检查的渲染预览。

## 当前进度标记

- 架构图将当前 v0.4 QA 与未来 Agents SDK 路径分开；未来路径与本地 Session / Audit 边界均使用虚线。
- 路线图将 `v0.4.2` 架构准备标为当前，将 `v0.5.0` Agents SDK 基础标为下一项，后续依次为 `v0.6.0` 至 `v1.0.0`。
- Agent 编排图只把 `Router -> Policy Handoff` 标为 `v0.5.0` 下一项；Claims 与 Complaint 保持后续状态，QA Agent 保持独立。
- 所有图中的解释性标签均使用中文；Agent、Reranking、Web、API、模型名称和命令参数保持技术原文。

## 验证

图示使用 `fireworks-tech-graph` skill 生成，并通过以下命令验证：

```bash
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/architecture.svg
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/roadmap.svg
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/agent-orchestration.svg
```

所有 SVG 均通过 XML、标记、碰撞、语义几何、构图和渲染验证。导出的 PNG 已进行视觉检查，以确认没有裁切、文字重叠或可读性问题。
