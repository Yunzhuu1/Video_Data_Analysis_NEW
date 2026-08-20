## Context

现状：12 表、7 指标（5 个 metric_daily + completion_rate/play_detail + engagement_rate/fact）、fact 1.2 万行（seed 42 确定性）。门禁靠 TableSchemaRegistry（12 表）+ 指标字典（7 指标）。评测 N=45（含 R1 17 个）。

目标：规模扩大让"生产感"与"架构演进可测性"成立。约束：seed 42 确定性（R1 可复现）、Python 主链路不改（合成器/门禁/记忆动态读 catalog/schema，只需验证）。

## Goals / Non-Goals

**Goals:**
- 指标 7→15、表 12→16、fact 数据量放大 + 真实业务模式（长尾/稀疏/异常/节日）。
- 新表进门禁注册表；新指标进字典/别名。
- 评测 N=45→~70，新用例含 golden_spec + R1 真值；新基线（既有 45 子集零回退）。

**Non-Goals:**
- **不做能力补全**（数值过滤/跨源多指标）——那是 C2 change；本 change 只扩数据与评测，若新用例触发合成器不支持（如跨源多指标），标记已知边界不硬解。
- 不做 schema linking 召回层（C3）——规模到位后单独做。
- 不做多租户/真实用户流量。

## Decisions

### D1：新增指标（8 个，7→15）
| metricCode | 口径 | 来源 |
|---|---|---|
| `comment_rate` / `like_rate` / `share_rate` | 各事件数 / 播放数（fact 派生比率） | user_behavior_fact |
| `avg_completion_ratio` | AVG 完播比例（区别于 completion_rate 的聚合口径） | play_detail |
| `creator_revenue` | 创作者收益（SUM 日收益） | creator_revenue 表 |
| `video_revenue` | 视频收益 | video_revenue 表 |
| `active_creator_count` | 活跃创作者数（DISTINCT） | user_behavior_fact JOIN creator_dim |
| `daily_active_users` | 日活跃用户数（DISTINCT user） | user_behavior_fact |

理由：覆盖 3 种新形态——比率派生（fact 内）、跨表收益（新表）、去重计数（fact 去重）——让合成器/门禁面对更真实的多态查询。

### D2：新增表（4 张，12→16）
| 表 | 关键列 | 表类型 |
|---|---|---|
| `creator_revenue` | creator_id/date/revenue/expense/profit | FACT |
| `video_revenue` | content_id/date/revenue | FACT |
| `user_retention` | user_id/date/is_active/is_retained | FACT |
| `content_quality` | content_id/quality_score/category | DIM（或 FACT 细分） |

理由：引入真实跨表关系（创作者→收益、视频→收益、用户→留存），评测可覆盖跨表 JOIN 类查询；门禁表类型需同步。

### D3：数据真实业务模式（DataInitializer，seed 42 确定性）
- **长尾**：头部 20% 创作者/视频占 80% 收益（收益分配偏 Zipf）。
- **稀疏**：美妆分类新创作者收益稀疏（部分天无记录）。
- **异常**：某日某视频收益异常峰值 + 某天数据断档（缺失日）——让 DQ/门禁面对异常。
- **节日效应**：保留 10/1-7 激增 + 增加春节（2024-02）效应（若数据跨年）。
- 确定性：全部由 seed 42 派生，**新数据重灌后可复现**（R1 真值稳定）。
- 理由：数据量本身不带来生产感，**分布与异常才带来**；也让 DQ（截断/缺失/异常检测）有真实输入。

### D4：门禁同步（TableSchemaRegistry）
- 注册 4 张新表 + 表类型（FACT/DIM）。
- 新表敏感列声明（如 creator_revenue.expense 为内部数据？——评估是否敏感）。
- 理由：门禁 AST 校验按注册表识别表/列，不注册 = 新表 SQL 全被误拦。

### D5：评测扩展（N=45→~70）
- 新增 ~25 个 golden cases：覆盖新指标（比率/收益/去重）、新表（跨表 JOIN）、新关系（创作者→收益、视频→收益）、真实分布（长尾/稀疏查询）。
- 每个新用例：golden_spec + **R1 expected_result（独立手工 SQL 取 seed 42 真值，truth_source 记录）**。
- **新基线**：--memory off 全量回归——**既有 45 例子集 L1-L4/R1 零回退**（子集对比，P2-1 口径）+ 新增 ~25 例独立报告。
- 新指标补 `aliases.yaml`（用户说法→code，新指标要"问得到"）。

### D6：验证
- 真实评测：--memory off N=~70 基线 + R1（新旧全量）；既有 45 子集零回退。
- 合成器/门禁对新表/新指标的查询验证（新用例能合成或按已知边界降级，不报未捕获错误）。

## Risks / Trade-offs

- **[Risk] 新指标跨源多指标用例触发合成器降级**（如"创作者收益+播放量"）→ 已知边界，标记 fallback，C2 处理（本 change 不硬解）。
- **[Risk] 数据放大后评测耗时增加**（~70 用例 × LLM）→ 回归接受更长耗时；新基线用 mock/real 组合控制。
- **[Risk] seed 42 扩数据破坏旧 R1 真值** → 旧用例真值不变（数据只增量，不重算旧数据）；新用例新真值。
- **[Risk] 表关系设计不合理**（收益表粒度/外键）→ D2 的粒度（creator_id+date 唯一）对齐 metric_daily 模式，门禁校验可验证。

## Migration Plan

1. schema.sql +4 表 → DataInitializer 灌数据（seed 42，真实分布）→ TableSchemaRegistry 注册。
2. metric_catalog.json +8 指标 → aliases.yaml 补新指标。
3. cases.yaml +~25 用例（golden_spec + 手工 SQL 取 R1 真值）。
4. 全量 pytest（Python 主链路零改动应绿）→ 新基线评测（N=~70，既有 45 子集零回退）。
5. metrics-report 更新（新基线）+ 开发日志。

## Open Questions

- 数据是否跨年（2024 春节效应）？→ 倾向保持 2023-10 单月（seed 42 已有模式），春节效应留后续。
- `creator_revenue.expense` 是否算敏感列（门禁 SENSITIVE_FIELD_ACCESS）？→ 评估后定，倾向不敏感（内部 demo）。
- 新用例是否触发 C2 的跨源多指标？→ 先标边界，C2 解锁后再扩。
