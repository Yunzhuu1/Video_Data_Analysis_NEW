## Context

`agent-eval-harness` 依赖 `semantic-resolve-node` 的 `ResolvedIntent`（golden_spec 与之一致）；mock eval 现状是假数据。本 change 把评测从"脚本"升级为"产品"：golden_spec + 比较器 + FakeLLM 录制回放 + 四层评分 + A/B 对比 + 回归门禁。

## Goals / Non-Goals

**Goals:**
- 口径正确率等核心指标变成可复现、可解释的实测数字（非目标值）。
- 测试/评测不依赖 API key（回放模式），CI 可跑、结果 100% 可复现。
- 输出真实 eval 报告 + 基线对比，支撑简历与面试叙事。

**Non-Goals:**
- 不做 LLM-as-judge 作为核心指标（可复现性优先；开放性回答质量可后续作为次要指标）。
- 不替代 `semantic-resolve-node`（本 change 只做测量，不改变图行为）。
- 不做 LangSmith 等外部平台集成。

## Decisions

- **决策 1：`golden_spec` schema 与 `ResolvedIntent` 完全同构**。schema：`{intent, metrics[], dimensions[], time_range{type, relative|absolute, granularity}, filters[{field,op,value}], ordering{field,direction,limit}}`。评测即对节点输出做确定性比对，避免"评测补丁"与"agent 契约"两套 schema。
- **决策 2：四层评分阶梯**。
  - L1 核心口径正确率：`metrics` 解析正确的用例占比（简历主打数字）；
  - L2 严格全字段正确率：所有字段全对才计 1（兜底）；
  - L3 平均字段匹配率：Σ(正确字段数/必需字段数)/用例数（迭代梯度信号）；
  - L4 分项正确率：维度/时间范围/过滤分别报（定位短板）。
- **决策 3：归一化与比较规则**。指标别名→代码；维度无序集合相等；时间范围相对→绝对（按固定 `eval_date` 展开）后比较：起点终点相同 + 长度差 ≤ 1 天 + 粒度一致，`none` vs 有区间算错；过滤归一为 `(field,op,value)` 集合；ordering 精确相等；intent 第一顺位。
- **决策 4：FakeLLM 录制回放**。hook 在 `LLMClient.complete_json`（现有唯一接缝）。`mode=record`：调真实 API 并把 `{hash(messages): response}` 写入 cassette 文件；`mode=replay`：查表返回，未命中即失败（提示重新录制）或返回注册的默认响应。支持手工编辑 cassette 注入错误（空 SQL/坏 JSON/retryable 错误）以覆盖分支。
- **决策 5：回放 vs 真实评测分离**。回放 = 回归测试（图逻辑正确性，CI）；真实评测 = 质量测量（出数字）。真实评测跑一次后录制，之后 CI 用回放回归；定期重跑真实评测刷新基线。
- **决策 6：A/B 对比为第一等公民**。`eval runner --mode real --config-a --config-b` 输出每个指标的 diff 表（如 grounding 前/后、路由前/后），这是简历叙事最有冲击力的形态。
- **决策 7：开放性/歧义用例单列**。无法唯一确定 spec 的问题不硬套 `golden_spec`，只统计端到端成功率，避免数字失真。

## Risks / Trade-offs

- [严格全字段正确率过低（时间范围归一化难）] → 这是特性不是缺陷：L4 分项归因能看到丢分在哪；先跑真实基线再定目标，不拍脑袋。
- [cassette 与 prompt 版本漂移（改 prompt 后回放失配）] → 未命中即报错强制重录；重录后跑 A/B 判断质量变化。
- [golden_spec 标注成本高] → 首批 20 条内完成，人工标注是评测体系固有成本；schema 复用 `ResolvedIntent` 使标注与节点输出同构，降低歧义。
- [eval_date 与模拟数据范围（2023-10）不一致] → `eval_date` 固定为 2023-10-14（落在数据范围内），相对时间按它展开。

## Migration Plan

1. 定义 `golden_spec` schema + `SpecComparator`（纯函数 + 单测）。
2. 实现 FakeLLM（record/replay cassette）。
3. `cases.yaml` 扩到 20+ 并补 `golden_spec`（含 7 条已草用例）。
4. runner 升级：回放模式跑真实图（FakeLLM）+ 四层评分 + 报告；真实模式跑基线。
5. A/B 对比输出；CI 门禁接入（ruff + pytest + mock eval）。
6. 真实评测跑一次基线，产出 `docs/eval-report.md` 真实数字。

## Open Questions

- 首批 golden set 的 20 条用例清单是否含歧义类（默认：含 3 条，单列统计）。
- `eval_date` 是否固定进 `cases.yaml` 顶层配置（默认：是，全局一个）。
