## 1. debug 透传（P0）

- [x] 1.1 Python `AnalyzeResponse` 增加可空 `resolvedIntent` / `sqlRetryCount`（pydantic alias 为 camelCase）
- [x] 1.2 `routes.py` 的 `analyze()` / `approve_run()` 从 graph state 透传这两个字段
- [x] 1.3 Spring `EngineAnalyzeResponse` 增加可空 `resolvedIntent` / `sqlRetryCount`
- [x] 1.4 `AnalysisReport` 增加 `debug` 字段（Map，默认 null，不影响现有消费方）
- [x] 1.5 `AgentController.analyze` 增加 `includeDebug` 参数（默认 false），true 时填充 `report.debug`
- [x] 1.6 eval runner `run_real_case` 请求加 `includeDebug=true`，从 `payload["debug"]` 读取 `resolvedIntent`
- [x] 1.7 Python route 测试：响应含 `resolvedIntent` / `sqlRetryCount`
- [x] 1.8 Java `AgentController` 契约测试：includeDebug=false → debug 为 null；true → debug 有值

## 2. 失败隔离（P0）

- [x] 2.1 runner 主循环逐用例 try/except，环境性异常（httpx 网络/超时/5xx/限流）标 `ERROR`
- [x] 2.2 聚合与报告新增「评测可用性 x/21」，`ERROR` 不计入 `judged` 并单列明细
- [x] 2.3 real 模式对可重试环境错误重试一次 + 退避
- [x] 2.4 测试：环境失败不中断整场、`ERROR` 不计入口径分母

## 3. 正交轴解耦（P0）

- [x] 3.1 runner CLI 改为 `--llm <mock|record|replay|real>` × `--platform <mock|real>`；`EVAL_LLM_MODE` / `PLATFORM_CALLS_ENABLED` 作为默认值来源
- [x] 3.2 非法组合校验（如 record + platform=real 拒绝）
- [x] 3.3 报告 header 记录 `llm_source` / `platform_source` / `model` / `eval_date` / cassette
- [x] 3.4 `run_real_case` 使用 cases.yaml 的 `eval_date` 而非硬编码 `2023-10-14`
- [x] 3.5 A/B compare 前校验两报告配置一致，不一致拒绝
- [x] 3.6 测试：语义层评测组合（llm=real, platform=mock）可跑通且报告自描述配置
- [x] 3.7 报告归档：JSON 写入 `docs/eval-reports/eval-{llm}-{platform}-{eval_date}.json`，MD 保留 `docs/eval-report.md` 最近快照

## 4. mock catalog 对齐（P1）

- [ ] 4.1 抽取共享指标定义（单数据源），Java `DataInitializer` 与 Python mock catalog 同源读取
- [ ] 4.2 覆盖测试：所有 golden 用例指标均存在于共享定义中
- [ ] 4.3 若跨语言读取成本过高，回退方案：Python 内联 7 指标 + 注释指向 `DataInitializer.METRICS` + 覆盖测试兜底

## 5. golden 质量与报告透明（P1）

- [ ] 5.1 修复 c01 等歧义用例（time_range 定死或标注开放性移出 judged）
- [ ] 5.2 报告 L1/L2/L3 带分母展示（如 `87% (13/15)`）

## 6. 文档（P1）

- [ ] 6.1 `EVALUATION.md` 更新：正交轴、失败语义三态、评测可用性、语义层评测与 real 评测命令
- [ ] 6.2 `README.md` 本地检查命令更新
