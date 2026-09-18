# README 图示

本文档记录 `v0.6.0` 的发布图。三张图均采用 Fireworks Tech Graph 的 Style 1 Flat Icon 参考、白色画布与清晰的当前/后续边界。

## 资源

- `docs/assets/architecture.svg`：当前 Copilot 的 `Policy Tool -> Evidence Ledger -> Citation Judge -> Runtime Gate` 证据链，和独立 QA 路径。
- `docs/assets/architecture.png`：架构图的本地 CairoSVG 预览。
- `docs/assets/agent-orchestration.svg`：固定 `Router -> Policy Agent` 与其后的证据链；不绘制尚未实现的 Handoff。
- `docs/assets/agent-orchestration.png`：编排图的本地 CairoSVG 预览。
- `docs/assets/roadmap.svg`：`v0.6.0` 标为当前，`v0.7.0` 标为下一项，并单独说明后续范围。
- `docs/assets/roadmap.png`：路线图的本地 CairoSVG 预览。

## 表达约束

- 绿色实线和实心状态表示当前已实现路径；灰色虚线分区只表示后续边界。
- Evidence Ledger 必须标为“当前进程、当前轮、内存”；它不是持久存储。
- Runtime Gate 只允许 `supported` 进入交付路径；其余 verdict 进入 `human_takeover`。
- 图中不得将 Claims、Complaint、持久 Session、审批、副作用工具或 Web/API 画为节点、接口或可用路径。

## 验证

每次更新图示均执行 SVG 的 XML、marker、箭头碰撞、语义几何、构图与渲染验证，并通过本地 CairoSVG 导出 PNG。导出后必须视觉检查文字、箭头、分区与图例，确认无裁切或重叠。
