## Why

当前 mock eval 是"假数据刷分"：`platform_calls_enabled=false` 时校验/执行/DQ 全返回写死数据，LLM 从未被调用，case 耗时 0ms；`EVALUATION.md` 中的指标（如 SQL 生成成功率 ≥90%）是未实测的目标值。目标是把 agent 变成"可评测、可回归、可观测"的工程系统（eval-driven development）。

## What Changes

- 引入 `golden_spec`：每个 golden case 增加结构化标准答案（`{intent, metrics, dimensions, time_range, filters, ordering}`），与 `semantic-resolve-node` 的 `ResolvedIntent` 共用同一 schema。
- 新增 `SpecComparator`：归一化（指标别名、维度集合、时间区间展开、过滤三元组）+ 四层评分（核心口径正确率 / 严格全字段正确率 / 平均字段匹配率 / 分项正确率）；时间容差规则：起点终点相同且长度差 ≤ 1 天。
- 新增 FakeLLM 录制回放：真实 LLM 调用录制为 cassette（按请求哈希），离线回放，不依赖 API key、可复现、CI 可跑；支持手工注入错误响应以覆盖 retry/fallback 分支。
- 指标集重新定义并实测：口径正确率、端到端成功率、自动修复成功率、高风险拦截率、单次成本、p50/p95 延迟。
- 支持 A/B 基线对比：同一 golden set 跑两个配置（如语义 grounding 前/后）并输出 diff。
- `cases.yaml` 扩到 20+ 条（复用 C01~C10 种子）并标注 `golden_spec`；eval 报告写入 `docs/eval-report.md`（真实数字）。
- CI 回归门禁：`pytest` + mock eval（回放模式）全绿才可合并。

## Capabilities

### New Capabilities
- `agent-eval`: 基于 golden_spec 的评测体系——确定性比较器、FakeLLM 录制回放、四层评分、A/B 对比与回归门禁。

### Modified Capabilities
<!-- 无既有 spec 需要修改 -->

## Impact

- 代码：`agent-engine/app/eval/{runner,metrics,comparator,fakellm}.py`、`cases.yaml`
- 依赖：新增录制回放所需序列化（无新增第三方依赖，标准库即可）
- 文档：`EVALUATION.md` 重写、`docs/eval-report.md` 更新
- 测试：`tests/test_eval_metrics.py` 扩展（比较器/回放用例）
