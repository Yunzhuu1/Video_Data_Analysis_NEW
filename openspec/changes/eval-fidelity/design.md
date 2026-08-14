## Context

真实评测 73.91%（17/23）的 6 个失败，拆解后三个根因：
1. **评测语义**：c04/c06/c10 被门禁正确拦截（事实表无时间范围/聚合重查询），但等待报告缺字段 → 判 FAIL。
2. **意图层缺口**：c18 意图=全量明细，但 LLM 生成的 SQL 恰好带 LIMIT+时间 → 门禁（只认 SQL）放行 → SUCCESS，拦截失效。
3. **回答质量**：c11/c17 的 LLM 报告缺 metrics/DQ 关键词。

## Goals / Non-Goals

**Goals:**
- 端到端评测如实反映系统能力（审批暂停不是失败；意图层拦截确定性）。
- 端到端 ≥ 90%。
- 回答质量兜底（c11/c17）。

**Non-Goals:**
- dimensions 抽取优化、门禁规则重构、记忆系统。

## Decisions

### D1: 评测语义——risk 用例拦截即 PASS + 其余类型自动放行补跑
- **risk 类型用例**（`expected_status=WAITING_APPROVAL`，如 c22/c19）：收到 WAITING_APPROVAL 即 PASS（拦截=正确行为），不要求报告字段。
- **其余类型**（c04/c06/c10 是 metric/text2sql）：若 runner 收到 WAITING_APPROVAL，**自动调用 `POST /api/agent/runs/{runId}/approval {"approved": true}` 放行**，等待引擎执行并产出报告，再继续字段/关键词检查 → 审批后完整链路得到验证，报告字段检查能通过。
- 备选（纯"拦截即 PASS"）：实现简单但 c04/c06/c10 不验证"审批通过后能否跑通"，报告字段检查失去意义 → 拒绝。
- 备选（不自动放行，改期望为 WAITING_APPROVAL）：把 c04/c06/c10 的期望改成 WAITING_APPROVAL 即 PASS → 丢失"审批后执行"的验证，且与 c22/c19 语义重复 → 拒绝。
- **评测保真度自证**：runner 报告增加 `auto_released` 计数/比例（非 risk 用例收到 WAITING_APPROVAL 后被自动放行的数量/占比）。自动放行可能掩盖"门禁过度拦截"——auto_released 比例偏高说明门禁在拦不该拦的查询，与端到端数字解耦，让"端到端上升"可辩护。

### D2: 意图层风险——gate 请求携带 intent，静态层结合 intent 判定
- `ResolvedIntent` 已有 `intent ∈ {aggregate, trend, ranking, detail}`；`SEMANTIC_RESOLVE` 出口把 `intent` 透传给 `platform.validate_sql(intent=...)` → `SqlValidateRequest` 增加 `intent` 字段 → `SqlStaticAnalyzer` 规则按 intent 增强：
  - **`intent=detail` 且 `intent.time_range` 缺失或 `type == "none"` → 无条件 APPROVAL_NEEDED**（与 SQL 形态无关）——注意 `semantic_resolver._normalize` 会把 time_range 缺省为 `{"type": "none"}`，故谓词必须覆盖 `type == "none"`，否则永不触发；解决 c18：其意图"查询所有播放明细"无时间范围，即便 LLM 写出 LIMIT+时间合规 SQL 也确定性审批。
  - `intent=detail` 且 `intent` 自带时间范围 → 按 SQL 检查（LIMIT+时间），保留"最近1小时播放明细"这类带范围 detail 查询正常走。
  - **聚合意图豁免 LIMIT**：`intent ∈ {aggregate, trend, ranking}` 或 SQL 含 GROUP BY/聚合函数 → `DETAIL_QUERY_WITHOUT_LIMIT` 不适用（聚合不返回明细行）；时间范围规则仍适用（事实表无时间范围 → 审批）→ 修 c04/c10 的"以错误理由拦截"。
- **意图-形态一致性（收紧）**：`intent ∈ {aggregate,trend,ranking}` 但 SQL 无 GROUP BY/聚合函数且触碰 FACT → `RETRYABLE`（语义说聚合、SQL 是明细形态 = LLM 写错，重写）。intent 信号双向使用（豁免 LIMIT + 收紧形态），规则自洽。
- **intent 可用性边界**：语义解析失败（`resolved_intent=None`）时 gate 退化为纯 SQL 判定，fallback 路径的 c18 类问题仍可能绕过——已知边界，接受（该路径由 SQL 级规则兜底）。不变式：合成失败降级时 `resolved_intent` 仍在 state（`semantic_resolve_node` 在 `acceptable=False` 时也写入），intent 照常透传。
- **产品决策（显式记录）**：聚合意图 + FACT 全扫仍会审批（c04/c10 落到计划层）——语义是"重查询需人审"，由 D1 自动放行兜评测；后续 change 候选：聚合意图 + GROUP BY 且 EXPLAIN 行数有界 → PASS。
- 备选（语义层出口标记 + 图路由，gate 不感知 intent）：图在 HARD_GUARD 前根据 intent 硬编码拦截 → 规则分散两处（Python 一处、Java 一处），且 c04/c10 的 LIMIT 豁免 Java 侧也难处理 → 拒绝。
- 落地：`SqlValidateRequest`/`SqlGateResult` 加 intent；Python `PlatformClient.validate_sql` 传 intent；`SqlStaticAnalyzer.analyze(sql, tables, intent)`。

### D3: 回答质量兜底
- `AnswerAgent._sanitize_metrics` 已有（净化为空列表）；新增：LLM 回答 metrics 为空但查询结果有数值列时，用 `_basic_metrics(columns, rows)` 兜底生成；`_fallback` 已带 DQ 警告，`_normalize` 需把传入的 `warnings`（含 DQ 警告）强制并入回答，确保关键词（如 "partial data"）出现在报告文本中。
- 注意：DQ 关键词断言针对的是报告**文本**（`json.dumps(final_report)` 检索），所以 DQ 警告需进入 `warnings` 字段即可被检出。

## Risks / Trade-offs

- [自动放行补跑可能掩盖"审批流本身"的问题] → risk 类型用例仍保持"拦截即 PASS"（严格路径），自动放行只用于其余类型，两条路径都覆盖。
- [intent 入参增加契约耦合] → intent 是 ResolvedIntent 既有字段，透传成本低；gate 对未知/空 intent 退化为现状（只认 SQL）。
- [聚合豁免 LIMIT 后 c04/c10 落到计划层继续拦] → 预期：无时间范围的聚合扫事实表 → 计划层 FULL_SCAN/FACT → 仍 APPROVAL → 由 D1 自动放行补跑覆盖，评测语义统一处理。

## Migration Plan

1. Java：`SqlValidateRequest`/`SqlGateService`/`SqlStaticAnalyzer` 支持 intent 入参 + 聚合豁免 LIMIT + detail 强制。
2. Python：`PlatformClient.validate_sql` 传 intent；`nodes.py` 透传 resolved_intent。
3. 评测：runner 自动放行补跑；cases.yaml 期望调整（c04/c06/c10 语义、c18 期望 WAITING_APPROVAL）。
4. AnswerAgent 回答兜底。
5. 全量回归 + 真实评测重跑 + 文档。
