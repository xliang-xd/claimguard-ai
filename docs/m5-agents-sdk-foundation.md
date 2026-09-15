# M5：Agents SDK 运行时基础

`v0.5.0` 交付最小可运行的客服 Copilot 基础。当前仅启用 `Router -> Policy Handoff`：Router 识别保单、保障责任、等待期和免责等条款解释意图，并只可转交给 Policy Agent。Policy Agent 的当前指令要求先调用 Policy Tool 检索条款，并仅据返回的条款证据起草；证据不足时应返回 `human_takeover`，证据充分时才输出以“客服草稿：”开头的 `draft_ready`。这是当前 Agent 指令和工具配置的行为，不是 Runtime 强制的不变量；Runtime 对实际工具调用及草稿与工具证据绑定的验证留待后续里程碑。

Claims、Complaint、审批、任何副作用工具、完整 Compliance Guard、Reranking 和 QA Citation Judge 仍未启用。现有 QA CLI 保持独立，默认离线，且 QA JSON 报告契约不变。

## 本地配置与边界

项目最低 Python 版本为 3.10，满足 `openai-agents>=0.14,<0.15` 的运行要求。Copilot 使用阿里云 Model Studio 的 Qwen 兼容 API；建议在中国大陆部署时保留默认 endpoint：

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

`DASHSCOPE_API_KEY` 只应通过本地被忽略的 `.env` 或显式进程环境变量提供。可选的 `CLAIMGUARD_DASHSCOPE_BASE_URL`、`CLAIMGUARD_ROUTER_MODEL` 和 `CLAIMGUARD_POLICY_MODEL` 用于本地覆盖。不要将 `.env`、`.claimguard/`、API Key 或审计文件提交到 Git。

OpenAI 托管 tracing 默认关闭。只有显式设置 `CLAIMGUARD_OPENAI_TRACING_ENABLED=true` 才会开启；默认未设置或设置为 `false` 时，Agents SDK 使用关闭 tracing 的 `RunConfig`。

默认审计路径是 `.claimguard/audit.jsonl`。每条审计事件包含运行结果所需的标识和状态，但拒绝原始客户消息、对话内容及任何凭据字段。`InMemorySessionStore` 仅保证同一进程内的多轮恢复；持久 Session、跨进程恢复和长期存储留待后续里程碑。

## 演示步骤

先使用现有本地 Qwen 配置创建知识索引。该命令会调用 Embedding 服务并把生成文件写入被忽略的 `.claimguard/`：

```bash
PYTHONPATH=src python3 -m claimguard.cli index data/knowledge/petcare-plus-policy-zh.md \
  --output .claimguard/petcare-plus-policy.json
```

然后运行 Copilot：

```bash
PYTHONPATH=src python3 -m claimguard.copilot_cli \
  --tenant-id demo-tenant --user-id agent-7 --session-id policy-demo-001 \
  --index .claimguard/petcare-plus-policy.json \
  "宠物投保后第二天就生病了，为什么不赔？"
```

受控演示的期望输出是 JSON，其中 `current_agent` 为 `Policy Agent`，且 `draft` 以“客服草稿：”开头。草稿仅依据检索条款是当前 Policy Agent 指令与工具配置的行为，而非 Runtime 层验证。不要把输出中的任何本地配置值保存到文档、fixture 或提交信息。

## 证据说明

当前实现将上述要求放在 `POLICY_INSTRUCTIONS`，并仅向 Policy Agent 配置 `policy_search_tool`；`CopilotRuntime._validated_output()` 只验证输出状态和草稿前缀，不检查工具调用或草稿与返回证据的对应关系。运行时工具证据验证因此明确后移。

## 验证分层

离线验证不读取 Key，也不发出网络请求：

```bash
git diff --check
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/claim-amount-dispute.json
```

索引创建和 Copilot 命令是受控的真实 Qwen smoke test，会使用已存在的本地配置和网络访问。运行前先完成离线验证；若本地配置、凭据或网络不可用，应保留离线验证证据并只报告不含凭据的安全阻塞原因。
