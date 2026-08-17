## MODIFIED Requirements

### Requirement: LLM 只做语义匹配，不写 SQL
`SEMANTIC_RESOLVE` 节点 SHALL 输出结构化 `ResolvedIntent`（指标/维度/时间范围/过滤/排序），不得直接产出 SQL。维度抽取 SHALL 遵循：`date` 属于时间粒度而非业务维度；"各分类/按分类"类问法 → `dimensions`；"X 类视频"类限定 → `filters`。

#### Scenario: 解析输出结构化意图
- **WHEN** 用户问题进入 `SEMANTIC_RESOLVE`
- **THEN** 节点输出 `ResolvedIntent`（含 `intent`、`metrics`、`dimensions`、`time_range`、`filters`、`ordering`），state 中不出现新 SQL

#### Scenario: date 不入 dimensions
- **WHEN** 用户问题为时间序列类（如"最近7天每天播放量"）
- **THEN** `dimensions` 不含 `date`；时间粒度表达在 `time_range.granularity`

#### Scenario: 各分类归维度
- **WHEN** 用户问题含"各分类/按分类/每类"且讨论指标
- **THEN** `dimensions` 包含对应分类维度（如 `category`），不放入 `filters`

#### Scenario: 类目限定归过滤
- **WHEN** 用户问题用"X 类视频/美食的"限定单一分类
- **THEN** 该限定放入 `filters`（如 `category=美食`），不放入 `dimensions`

#### Scenario: 多分类对比归维度+过滤
- **WHEN** 用户问题用"对比/比较 A 和 B 分类"对比多个分类
- **THEN** `dimensions` 含 `category` 且 `filters` 含 `category IN (A,B)`（区别于单分类限定的 `filters =`）
