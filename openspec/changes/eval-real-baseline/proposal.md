## Why

当前 real 评测无法产出可信基线：`resolved_intent` 未透传到评测端，导致 `--mode real` 下 L1~L4 恒为 0%；单条用例超时/网络错误会中断整场 21 条评测；`--mode` 把"LLM 来源"与"平台来源"两个正交维度绑死，无法在无 MySQL 环境做语义层评测；mock catalog（3 指标）与真实种子（7 指标）不一致、golden 用例存在歧义，导致基线数字不可信。

## What Changes

- **观测数据透传**：Python `AnalyzeResponse` 与 Spring `EngineAnalyzeResponse` 增加可空 `resolvedIntent` / `sqlRetryCount`；`/api/agent/analyze` 增加 `includeDebug` 参数（默认 `false`，不开时响应与现状完全一致，不破坏既有契约）；eval runner 以 `includeDebug=true` 读取真实语义解析结果。
- **失败隔离**：runner 逐用例 try/except，环境性失败（超时/网络/限流）标 `ERROR`、不计入 `judged`、报告单列；新增「评测可用性 x/21」指标；real 模式对超时/限流重试一次并退避。
- **正交轴解耦**：`--mode` 拆为 `--llm <mock|record|replay|real>` × `--platform <mock|real>` 两个独立参数，解锁"真实 LLM + mock 平台"的语义层评测（无 MySQL 也可先出 L1~L4）；报告头部记录两轴配置，保证只有同配置的数字可 A/B 对比。
- **mock catalog 对齐**：mock catalog 与真实种子共用一份指标定义（单数据源），并加测试断言 golden 用例覆盖的指标都在 catalog 内。
- **golden 质量**：修复歧义用例（如 c01 趋势题 time_range 未定死），报告 L1 等指标带分母（如 `87% (13/15)`）。
- **明确暂缓**：cassette 版本化与 CI 门禁（仓库暂无 CI，列为 P2，不在本 change 范围）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `agent-eval`: 增加 real 评测可用性要求——观测数据透传（debug 通道）、失败语义三态（PASS/FAIL/ERROR）、正交运行轴（LLM 来源 × 平台来源）、mock 数据与真实对齐、基线报告可信（配置自描述 + 分母透明）。

## Impact

- 代码：
  - `agent-engine/app/api/schemas.py`、`agent-engine/app/api/routes.py`
  - `agent-engine/app/eval/runner.py`
  - `src/main/java/com/yunzhu/video_data_analysis/dto/EngineAnalyzeResponse.java`、`AnalysisReport.java`
  - `src/main/java/com/yunzhu/video_data_analysis/controller/AgentController.java`
- 测试：Python routes/eval 测试（debug 透传、失败隔离、正交轴）、Java `AgentController` 契约测试（includeDebug 开/关）。
- 文档：`EVALUATION.md`、`README.md`。
- 备注：`agent-eval` 能力定义于已完成的 `agent-eval-harness` change（delta 尚未 sync 到主 specs）。本 change 在其上追加 real 评测要求；建议落地前先 `openspec sync-specs` 把既有 delta 同步进主 specs，或在 apply 阶段一并处理。
