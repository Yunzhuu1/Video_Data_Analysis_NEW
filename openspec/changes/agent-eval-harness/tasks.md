## 1. golden_spec 与比较器

- [x] 1.1 定义 `golden_spec` schema（`app/eval/schemas.py`），与 `ResolvedIntent` 同构
- [x] 1.2 实现 `app/eval/normalizers.py`：指标别名→代码、维度代码、时间区间展开（按 `eval_date`）、过滤三元组
- [x] 1.3 实现 `app/eval/comparator.py`：四层评分（核心口径/严格全字段/平均字段匹配/分项），时间容差长度差 ≤ 1 天
- [x] 1.4 比较器单测：时间容差、多约束/漏约束、维度顺序、别名归一、四层输出

## 2. FakeLLM 录制回放

- [x] 2.1 实现 `app/eval/fakellm.py`：record/replay 两种模式，cassette 按请求哈希存取
- [x] 2.2 `LLMClient.complete_json` 可注入 FakeLLM（record 时透传真实调用并落盘；replay 时查表返回）
- [x] 2.3 支持手工 cassette：空 SQL/坏 JSON/retryable 错误注入
- [x] 2.4 测试：回放确定性（两次一致）、未命中报错、错误注入覆盖 retry/fallback 分支

## 3. 用例集扩充

- [x] 3.1 `cases.yaml` 扩到 20+ 条，复用 C01~C10 并补 `golden_spec`（含 7 条已草用例：趋势/聚合/相对时间/指标/过滤/TopN/对比）
- [x] 3.2 标注开放性用例（不设 `golden_spec`，单列）
- [x] 3.3 `cases.yaml` 顶层固定 `eval_date`（2023-10-14）

## 4. Runner 升级与报告

- [x] 4.1 `runner.py` 支持 `--mode replay`（FakeLLM + 真实图）与 `--mode real`（真实 LLM）
- [x] 4.2 输出四层评分 + 端到端成功率 + 自动修复成功率 + 高风险拦截率 + 成本/延迟（p50/p95）
- [x] 4.3 支持 A/B：`--baseline-config` 与 `--candidate-config` 输出逐指标 diff
- [x] 4.4 报告写入 `docs/eval-report.md`；真实模式跑一次基线，替换掉 mock 假数据报告

## 5. 回归门禁与文档

- [x] 5.1 CI/本地检查：`ruff` + `pytest` + mock eval（replay）全绿
- [x] 5.2 重写 `EVALUATION.md`：新指标定义（含计算口径）、目标改为"先实测后定标"
- [x] 5.3 更新 `README.md` 检查命令与 `docs/` 评测章节
