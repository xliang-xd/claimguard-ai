# README 图示

本文档记录截至 `v0.4.1` 更新的技术图。`v0.4.1` 将解释性标签本地化为中文，不改变图中标注的 `v0.4.0` 功能边界。

## 资源

- `docs/assets/architecture.svg`：独立展示索引构建与查询期 QA 路径，包括确定性规则、可选检索、可选语义质检、证据验证和去重。
- `docs/assets/architecture.png`：用于视觉检查的渲染预览。
- `docs/assets/roadmap.svg`：从 `v0.1.0` 到计划中的作品集演示的版本路线图，`v0.4.0` 语义质检标记为当前。
- `docs/assets/roadmap.png`：用于视觉检查的渲染预览。
- `docs/assets/agent-orchestration.svg`：已实现的 QA 工作流，以及延后的 Copilot 和高级判断能力，并标出国产模型默认配置。
- `docs/assets/agent-orchestration.png`：用于视觉检查的渲染预览。

## 当前进度标记

- 架构图将 `v0.4.0` 语义质检标为当前能力，并将索引创建与查询期检索分开。
- 路线图将 `v0.4.0` 语义质检标为当前实现阶段；Citation Judge、Reranking、Copilot 和 API 属于未来范围。
- Agent 编排图将可选语义质检标为当前，并只在延后泳道中展示 Copilot Agent。
- 所有图中的解释性标签均使用中文；Agent、Reranking、Web、API、模型名称和命令参数保持技术原文。

## 验证

图示使用 `fireworks-tech-graph` skill 生成，并通过以下命令验证：

```bash
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/architecture.svg
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/roadmap.svg
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/agent-orchestration.svg
```

所有 SVG 均通过 XML、标记、碰撞、语义几何、构图和渲染验证。导出的 PNG 已进行视觉检查，以确认没有裁切、文字重叠或可读性问题。
