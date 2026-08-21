## Why

项目当前规模（12 表、7 指标、fact 1.2 万行）使架构演进点无法被真实暴露：全量指标进 prompt 仍够用（schema linking 无可测收益）、查询类型单一（无数值过滤/跨表收益类查询）、评测样本有限。扩大数据规模是"让项目贴近生产、不 toy"的第一步——**先让问题真实发生，优化才有意义**（呼应 metric-recall 搁置决策）。

## What Changes

- **指标 7 → 15**：新增 8 个业务指标（评论率/点赞率/分享率、平均完播率、创作者收益/视频收益、活跃创作者数、日活跃用户）——覆盖新表与派生口径。
- **表 12 → 16**：新增 `creator_revenue`（创作者收益）、`video_revenue`（视频收益）、`user_retention`（用户留存）、`content_quality`（内容质量）——引入真实跨表关系（收益按创作者/视频、留存按用户）。
- **数据放大（旧窗口不变）+ 真实业务模式**：放大通过**新增日期区间（2023-11/12）与新表**实现，**既有 2023-10 数据字节级不变**（旧 R1 真值稳定、零回退成立）；真实业务模式（长尾 80/20、稀疏、异常峰值/断档、复用 10/1-7 节日效应）——让 DQ/门禁/合成器面对真实分布。
- **门禁同步**：`TableSchemaRegistry` 注册 4 张新表（表类型 FACT/DIM）——AST 校验/计划层能识别新表。
- **评测扩展**：新 golden cases（新指标/新表/新关系，~25 个）→ N=45 → ~70；新用例标 golden_spec + **R1 真值**；重定**新基线**（既有 45 例子集零回退 + 新增独立报）。
- **别名同步**：`aliases.yaml` 补新指标的用户说法映射（新指标要"问得到"）。

## Capabilities

### New Capabilities
- （无新 capability——数据/评测扩展，属既有能力规模化）

### Modified Capabilities
- `chatbi-mainline`: 指标字典/数据模型扩展——新指标与新表进入 catalog/schema，主链路可查询。
- `agent-eval`: 评测数据规模扩展——golden cases N=45→~70、新指标/表/关系覆盖、R1 真值扩展、新基线。

## Impact

- `src/main/resources/schema.sql`：+4 张表 DDL。
- `src/main/java/.../config/DataInitializer.java`：新表灌数据 + 数据放大 + 真实业务模式（seed 42 确定性）。
- `src/main/java/.../semantic/TableSchemaRegistry.java`：注册新表。
- `src/main/resources/metric_catalog.json`：+8 指标。
- `agent-engine/app/eval/cases.yaml`：+~25 新用例（golden_spec + expected_result）。
- `agent-engine/app/eval/aliases.yaml`：新指标别名。
- `docs/metrics-report.md`：新基线（N=~70）；`docs/开发日志.md`。
- Python 主链路：合成器/门禁/记忆无需改动（读 catalog/schema，动态适配），仅验证。
