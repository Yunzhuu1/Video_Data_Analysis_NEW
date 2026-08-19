## Context

评测体系已具备：golden_spec（L1-L4 语义层）、N=45 基线、mock/replay/real 三模式、记忆/多指标等能力回归。但**只比 intent，不比最终结果**。关键事实：
- mock 平台 `execute_sql` 返回写死假行（`{"date": "2026-01-01", "category": "demo", "total_plays": 100}`），与 SQL 无关 → mock 下结果断言无意义。
- `DataInitializer` 用固定随机种子 42 + 刻意业务模式（10/1-7 激增、10/8-10 下降）→ 真实 MySQL 数据确定、可复现 → expected_result 可预先确定。
- cases.yaml 现有字段无 expected_result（有 expected_sql_contains / golden_spec）。

## Goals / Non-Goals

**Goals:**
- 结果级正确率 R1（real 平台），与 L1-L4 并列、端到端口径不变。
- 分层断言（exact/trend_pattern/top_set）——严谨且不脆弱（趋势/排名用例长期不红）。
- 抓出"L1 对 + R1 错"（解析对但 SQL 错）的 bug，交叉诊断。

**Non-Goals:**
- mock 平台结果断言（假数据，N/A）。
- 全量 45 用例结果断言（MVP 只做 10-15 个可确定用例，扩展留后续）。
- 结果数值的自动化"对账"（不反查 seed 推导，用先跑取真值）。
- detail/歧义用例断言。

## Decisions

### D1：断言分层（按 intent 类型）
| intent | 断言 | 判定 |
|---|---|---|
| aggregate | `{type: "exact", value, tolerance}` | 数值 |actual-value| ≤ tolerance（如 1%） |
| trend | `{type: "trend_pattern", points}` | 关键点方向/激增下降模式匹配（seed 42 刻意模式） |
| ranking | `{type: "top_set", items, ordered?}` | 集合命中（必选）+ 顺序（可选） |
| detail/歧义 | 不断言 | R1=N/A |

理由：精确值对趋势/排名脆弱（一个值变即红）；方向/集合断言既严谨又稳定——结果级评测"长期不红"的关键。

### D2：R1 独立维度
- R1 = 结果断言通过数 / 可断言用例数（real 平台，judged 口径）。
- 与 L1-L4 并列报告；端到端（现有 95.56% 口径）不变。
- **L1 错 → R1=N/A**（结果对也是碰巧，避免假阳性）；`L1 对 + R1 错` 单列 = 合成器/SQL 生成 bug 的最直接信号。
- 理由：两套数字各自成立 + 交叉诊断价值。

### D3：expected_result 来源与格式
- 来源：先跑一次 real 评测（或手工 SQL）确认真实值 → 写入 cases.yaml `expected_result`。
- 格式（按 D1 类型）：
  ```yaml
  expected_result:
    type: exact
    value: 12345
    tolerance: 0.01
  # 或
  expected_result:
    type: trend_pattern
    points: [{"date": "2023-10-01", "direction": "up", "magnitude": "spike"}]
  # 或
  expected_result:
    type: top_set
    items: ["content_3", "content_4"]
    ordered: true
  ```
- 数据确定性（seed 42）保证取真值后稳定可复现。

### D4：平台行为
- mock/replay：R1=N/A（假数据无意义），只评 L1-L4（现状不变）。
- real：执行真实 SQL → 结果断言 → R1。
- 评测命令：`--llm real --platform real`。

### D5：MVP 范围
- 从 c01/c02/c03/c05 等结果可确定用例中挑 10-15 个（aggregate/trend/ranking 各覆盖）。
- 歧义题（n19/n23 类）、detail（c18/c19 类）、跨源多指标（n02）不加 expected_result。
- 理由：验证 R1 方法论跑通，再决定扩展全量。

## Risks / Trade-offs

- **[Risk] 精确值对数据变动敏感**（真实数据若重灌变化）→ 小容差 + seed 42 确定性 + 报告注明"结果基准取自 seed 42 数据"。
- **[Risk] 趋势方向误判**（噪声使方向不稳）→ 方向断言用关键点（激增/下降模式）而非逐点，seed 42 的刻意模式可稳定断言。
- **[Risk] 取真值过期**（数据初始化逻辑变更）→ 取真值脚本 + 报告版本化（记录取真值日期）。
- **[Risk] R1 与 L1 关系被误读**（L1 错 R1=N/A 可能被当"缺数据"）→ 报告明确 N/A 语义（不可判定，非失败）。

## Migration Plan

1. ResultComparator（纯新增模块 + 单测）。
2. 挑 10-15 用例 + 跑一次取真值 → cases.yaml 标 expected_result。
3. runner R1 聚合/报告/交叉诊断 + 单测。
4. real 评测验证 R1 + --memory off N=45 回归零回退。
5. metrics-report + 开发日志；无部署（评测侧改动，运行时零行为变化）。

## Open Questions

- 容差取值（1%？绝对值？）→ 取真值时看数值量级定，MVP 用相对 1%。
- 趋势方向判定的幅度阈值（多少算"激增"）→ 用 seed 42 模式标定（+50% 激增、-40% 下降）。
- 扩展全量用例的结果断言 → 后续独立 change（需先评估歧义/detail 的可断言性）。
