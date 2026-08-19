# 语义解析与确定性合成

## Purpose

语义解析与确定性合成：LLM 只做语义匹配，SQL 由确定性合成器产出，指标字典落地，长尾问题降级 raw SQL。

## Requirements

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

### Requirement: SQL 由确定性合成器生成
`SQL_SYNTHESIZE` 节点 SHALL 依据 `ResolvedIntent` 与 `metric_definition`（formula/source_table）确定性合成 SQL；相同 intent SHALL 生成相同 SQL；合成 SQL SHALL 引用真实表名并声明表别名，可在真实数据库上解析执行。合成器 SHALL 支持**同源表多指标聚合**（多个指标经 `_resolve_path` 后全部落在 `metric_daily` 列路径时，单 FROM + 多 SELECT 表达式列，共享 group-by/time/filter）；非 metric_daily 路径多指标（跨源或事实路径）与多指标 ranking/detail SHALL 明确降级（SynthesisError → raw SQL）。`time_range.type == "relative"` 时，合成前 SHALL 以**数据末日为锚**展开为 absolute 区间（含端点），合成 SQL 含时间过滤。

#### Scenario: 同意图同 SQL
- **WHEN** 两次输入相同的 `ResolvedIntent`
- **THEN** 合成器产出完全一致的 SQL 文本

#### Scenario: 合成 SQL 可复验
- **WHEN** 合成器产出 SQL
- **THEN** 该 SQL 可通过 `SQL_HARD_GUARD` 校验（或返回明确校验失败信息）

#### Scenario: 合成 SQL 引用真实表名
- **WHEN** 合成器基于 `metric_definition.sourceTable` 合成 SQL
- **THEN** FROM 子句包含真实表名与别名声明（如 `FROM metric_daily md`），且该 SQL 可在真实 MySQL 上解析执行，不得出现未声明别名的 `FROM md`

#### Scenario: 同源表多指标聚合
- **WHEN** ResolvedIntent 的 metrics 经 `_resolve_path` 后全部落在 `metric_daily` 列路径（如 metric_daily 的 total_plays + total_likes），且 intent ∈ {aggregate, trend}、共享同 group-by 集
- **THEN** 合成单 FROM 多 SELECT 列 SQL（每列 `agg_expr AS code`），在真实数据库可解析执行

#### Scenario: 跨源表多指标降级
- **WHEN** metrics 来自不同 source_table（如 play_detail + user_behavior_fact）
- **THEN** 抛 SynthesisError，节点降级 raw SQL 生成（sql_source=fallback），不产出错误 SQL

#### Scenario: 约束显式失败
- **WHEN** 多指标但 intent 为 ranking/detail，或维度/时间/过滤/排序不一致
- **THEN** 抛 SynthesisError（显式失败优于产出错误 SQL）

#### Scenario: 相对时间展开
- **WHEN** ResolvedIntent 的 time_range 为 relative（如 {amount: 7, unit: "day"}）
- **THEN** 合成前展开为 absolute 区间（锚点=数据末日，含端点：最近7天 = 末日往前 6 天），合成 SQL 含 `WHERE <timeField> BETWEEN start AND end`

#### Scenario: 锚点查询失败降级
- **WHEN** 数据末日锚点查询失败（网络/权限）
- **THEN** 保持 relative（合成器现状），记录 warning 且不打断主链路；R1 侧以 value_mismatch 暴露（不静默）

### Requirement: 指标字典落地
系统 SHALL 提供 `metric_definition` 表（含 `metric_code` 唯一键、`formula`、`dimensions`、`time_granularity`、`source_table`）与 `MetricCatalogService`，并通过 `/internal/metrics/{code}` 对外提供指标定义查询。

#### Scenario: 按代码查指标
- **WHEN** 调用 `/internal/metrics/total_plays`
- **THEN** 返回公式、可选维度、时间粒度与 `source_table`

### Requirement: 长尾问题降级 raw SQL
当 `SEMANTIC_RESOLVE` 无法解析（低置信/无候选/覆盖不到）时，系统 SHALL 降级到 `SQL_GENERATE`（原始 LLM SQL）+ 硬校验 + 重试，并标记 `source=fallback`。

#### Scenario: 解析失败降级
- **WHEN** `SEMANTIC_RESOLVE` 输出低置信或空候选
- **THEN** 条件边进入 `SQL_GENERATE`，生成结果标记 `source=fallback`，继续走护栏与执行

### Requirement: 数据模型 DDL 可复现
所有 mock 表（`user_behavior_fact`/`content_dim`/`creator_dim`/`user_dim`/`time_dim`/`activity_dim`/`metric_definition`/`metric_daily` 等）的建表语句 SHALL 收编进 `src/main/resources/schema.sql`，`DataInitializer` 仅负责种子数据。

#### Scenario: 空库可初始化
- **WHEN** 在空 MySQL 实例上执行 `schema.sql` 后再运行 `DataInitializer`
- **THEN** 所有表存在且种子数据注入成功，无"幽灵表"报错

### Requirement: 意图层风险信号
`SEMANTIC_RESOLVE` SHALL 把 `ResolvedIntent` 的 `intent` 透传给 SQL 门禁，使拦截可结合意图判定，不依赖 LLM 生成 SQL 的形态。

#### Scenario: detail 且意图无时间范围强制审批
- **WHEN** `ResolvedIntent.intent=detail` 且 `intent.time_range` 缺失或 `type == "none"`
- **THEN** 门禁返回 `APPROVAL_NEEDED`（与 LLM 生成的 SQL 形态无关；注意 time_range 有 `{"type":"none"}` 默认值，type=none 即视为无时间范围）

#### Scenario: detail 且意图带时间范围
- **WHEN** `ResolvedIntent.intent=detail` 且 `intent.time_range` 存在
- **THEN** 门禁按 SQL 检查（LIMIT + 时间范围），不无条件拦截

#### Scenario: 聚合意图豁免 LIMIT
- **WHEN** `ResolvedIntent.intent ∈ {aggregate, trend, ranking}` 或 SQL 含 GROUP BY/聚合函数
- **THEN** `DETAIL_QUERY_WITHOUT_LIMIT` 不适用（聚合不返回明细行）；时间范围规则仍生效

#### Scenario: 意图-形态一致性
- **WHEN** `intent ∈ {aggregate,trend,ranking}` 但 SQL 无 GROUP BY/聚合函数且触碰 FACT 表
- **THEN** 门禁返回 `RETRYABLE`（LLM 形态写错，重写）

### Requirement: 语义记忆检索与写入
`SEMANTIC_RESOLVE` SHALL 在调用 LLM 前先检索语义记忆：命中（高相似）直接复用历史 ResolvedIntent（含 metrics 一致性校验），近命中注入 few-shot 示例，未命中走 LLM；记忆写入 SHALL 仅发生在全链路成功之后，且记忆不直接进入 SQL。检索 SHALL 采用**语义 + 词面多信号融合**（embedding 语义 cosine 为主、BM25 词面为辅），并保留**精确匹配快路径**；embedding 模型不可用 SHALL 降级为文本相似度检索（行为不劣于现状）。metrics 一致性校验 SHALL 支持**指标表达映射**（别名表/表达指纹）扩展匹配，不再仅依赖问题文本中的 catalog 指标名字符串包含。

#### Scenario: 精确匹配快路径
- **WHEN** 规范化问题与记忆库某条目 `norm_question` 完全相等
- **THEN** 直接判为命中（score=1.0，不依赖 embedding 模型），复用存储的 ResolvedIntent，`sql_source=memory`

#### Scenario: 记忆命中直通
- **WHEN** 规范化问题与记忆库条目**多信号融合相似度** ≥ 阈值且 catalog 校验通过且 **metrics 一致性校验通过**（问题文本匹配到的指标名与存储 metric_codes 一致）
- **THEN** `SEMANTIC_RESOLVE` 不调用 LLM，直接复用存储的 ResolvedIntent，`sql_source=memory`

#### Scenario: 相似但不同指标不误命中
- **WHEN** 问题文本匹配到某指标名但存储条目的 metric_codes 不一致（如"最近7天点赞量" vs 存储的"播放量"）
- **THEN** 不直通复用，降级为近命中注入或未命中

#### Scenario: 近命中注入示例
- **WHEN** 多信号融合相似度处于注入区间
- **THEN** 历史 (question→intent) 示例注入语义 prompt（≤3 条），LLM 照常解析

#### Scenario: embedding 不可用降级
- **WHEN** embedding 模型加载/推理失败（网络、依赖、模型缺失）
- **THEN** 检索降级为文本相似度（difflib）双阈值，主链路不受影响

#### Scenario: 记忆写入条件
- **WHEN** 一次语义路径 run 全链路成功（执行成功 + DQ 通过/警告）
- **THEN** 该 run 的规范化问题与 ResolvedIntent 写入记忆库（upsert）；失败 run 不写入

#### Scenario: 记忆失效
- **WHEN** 记忆条目引用的指标不在当前 catalog（口径变更）、解析规则哈希已变化、或 embedding 模型版本已变化
- **THEN** 该条目不参与命中（口径变更条目删除；embedding 模型变更条目重算）

#### Scenario: 表达映射下的一致性校验
- **WHEN** 命中条目的 metric_codes 与问题文本经表达映射（别名/指纹）判定出的指标 ID 一致
- **THEN** 一致性校验通过，可直通；映射判定为空时仍降级（不直通）

### Requirement: 记忆命名空间隔离
语义记忆 SHALL 按 namespace 读写：`/analyze` 请求可携带 `memoryNamespace`（默认 `"default"`），语义解析读路径与写钩子 SHALL 按该 namespace 读写记忆，使 eval/场景记忆与真实记忆互不污染。

#### Scenario: 默认 namespace
- **WHEN** 请求未指定 `memoryNamespace`
- **THEN** 记忆读写使用 `"default"` namespace，与既有行为一致

#### Scenario: 指定 namespace 隔离
- **WHEN** 请求指定 `memoryNamespace=eval-xxx`
- **THEN** 读路径只检索该 namespace 的记忆，写钩子只写入该 namespace；不同 namespace 之间互不可见

#### Scenario: 记忆控制端点
- **WHEN** 内部调用 `POST /internal/memory/seed`（按 namespace 预置）或 `POST /internal/memory/clear`（按 namespace 清空）
- **THEN** 服务器记忆按 namespace 更新，端点需内部 token 校验，且 **seed 拒绝写入 `default` namespace**（生产记忆仅由写钩子沉淀）
