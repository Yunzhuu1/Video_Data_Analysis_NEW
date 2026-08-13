## Context

当前评测系统（`agent-engine/app/eval/`）已具备 golden_spec + 四层评分 + FakeLLM 录制回放 + A/B 对比，但 real 模式存在结构性缺口：

1. `resolved_intent` 只存在于 Python graph state，未进入 `AnalyzeResponse` / `EngineAnalyzeResponse` / `AnalysisReport` 任何一层 API 契约，`run_real_case` 读取恒为空 → L1~L4 全 0%。
2. runner 主循环 `[await run_case(...) for ...]` 无失败隔离，单条用例异常中断整场评测。
3. `--mode mock|replay|real` 把"LLM 来源"与"平台来源"两个正交维度绑死，缺少"真实 LLM + mock 平台"组合（无 MySQL 的语义层评测）。
4. mock catalog（3 指标）与真实种子（7 指标）不一致；golden 用例存在歧义（c01 趋势题 time_range 未定死）。

约束：业务契约（`AnalysisReport`）面向真实用户，不能被评测观测数据污染；仓库无 CI；用户决策——语义层保持最低投入（指标字典不扩），数字可信优先。

## Goals / Non-Goals

**Goals:**
- `--mode real`（及"真实 LLM + mock 平台"组合）能产出可信的 L1~L4 基线数字。
- 评测可复现：报告自描述运行配置（LLM 轴 × 平台轴 × eval_date），只有同配置可 A/B。
- 评测可运行：单条环境失败不中断整场，且不污染业务失败统计。

**Non-Goals:**
- 不扩展指标字典（保持 7 个，语义层最低投入）。
- 不做 cassette 版本化与 CI 门禁（仓库暂无 CI，P2 暂缓）。
- 不新增第三方依赖；不涉及数据库 schema 变更。
- 不重构既有 mock/replay 路径的评分逻辑（比较器/归一化不动）。

## Decisions

### D1: 观测数据走独立 debug 通道（includeDebug），不污染业务契约

评测需要的 `resolved_intent`/`sqlRetryCount` 是观测载荷，不是业务报告内容。

```text
Python AnalyzeResponse      + resolvedIntent / sqlRetryCount（可空，alias=camelCase）
Spring EngineAnalyzeResponse + 同名字段（可空，Jackson 缺省为 null）
Spring AnalysisReport        + debug: Map<String,Object>（默认 null）
/api/agent/analyze           + includeDebug 参数（默认 false）
                              true  → report.debug = {resolvedIntent, sqlRetryCount}
                              false → 响应与现状完全一致
eval runner                  includeDebug=true，读 payload["debug"]["resolvedIntent"]
```

- 备选 A：直接把 `resolvedIntent` 做成 `AnalysisReport` 业务字段。否决：业务 DTO 语义被评测元数据污染，前端/消费者契约含义模糊。
- 备选 B：另开 `/internal/eval/analyze` 独立评测入口。否决：多一条与用户路径并行的链路，两端易漂移；且会丢失"测的就是用户真实体验"的意义。
- 契约测试：Python route 断言响应带 `resolvedIntent`；Java `AgentController` 断言 includeDebug=false → debug 为 null（防回归）、true → debug 有值。

### D2: 正交轴解耦（--llm × --platform）替代 --mode

两个独立维度，runner 组合出合法矩阵，报告头部记录两轴配置：

| 组合 | 用途 |
|---|---|
| llm=mock, platform=mock | 图逻辑/降级路径自测（原 --mode mock） |
| llm=replay, platform=mock | CI/本地回归，不花 token（原 --mode replay） |
| llm=real, platform=mock | **语义层评测**：无 MySQL 也能出 L1~L4（本 change 新增） |
| llm=real, platform=real | 完整端到端定标（原 --mode real） |

- 备选：保持 `--mode` 并硬编码 4 个组合枚举。否决：每加一个组合就要改 CLI 与文档；两轴解耦后"语义层评测"是自然产物而非特例。
- `EVAL_LLM_MODE` 环境变量语义保留，作为 `--llm` 的默认值来源；`--platform` 覆盖 `PLATFORM_CALLS_ENABLED`。
- 报告 header 输出 `llm_source / platform_source / model / eval_date / cassette`，A/B compare 前校验两报告配置一致。

### D3: 失败三态（PASS / FAIL / ERROR）

- `PASS`：业务成功。
- `FAIL`：业务失败（解析错、合成失败、状态不符）→ 正常参与评分。
- `ERROR`：环境性失败（httpx 网络/超时/5xx/限流）→ 不计入 `judged`，报告单列，计入「评测可用性 x/21」。
- runner 主循环逐用例 try/except；real 模式对可重试环境错误重试一次 + 退避。
- 备选：环境失败直接中断整场（现状）或按业务失败计 0 分。前者毁整场，后者污染基线，均否决。
- 判定边界：ERROR 只捕获异常类型（`httpx.HTTPStatusError`/`TransportError`/`TimeoutException`），业务路径的普通返回仍走正常判分，避免误伤。

### D4: mock catalog 与真实种子单数据源

mock 与真实指标定义收敛到一份共享文件（YAML/JSON），Java `DataInitializer` 与 Python `PlatformClient` mock 同源读取；并加测试断言 golden 用例覆盖的指标都在 catalog 内。

- **位置与格式（已定）**：`src/main/resources/metric_catalog.json`，JSON 格式——Python 无 PyYAML 依赖，两侧均用标准库 `json`，零新增依赖。
  - Java `DataInitializer` 以 classpath 读取（`CommandLineRunner`，对运行 cwd 不敏感），种进 MySQL `metric_definition`。
  - Python `PlatformClient` mock 以仓库根相对路径读取（runner 已用 `Path(__file__).resolve().parents[3]` 定位仓库根）。
  - JSON 字段为 `DataInitializer.METRICS` 超集（code/name/definition/formula/dimensions/granularity/source_table/time_field/fact_event_type/fact_event_filter），各消费方按需取用。
- 否决的备选：仓库根 `config/`（Java 文件系统读取依赖 cwd，脆）；YAML（Python 需新增依赖）；内联 Python（就是漂移来源，仅作最后兜底）。

### D5: 语义层最低投入（scope 原则）

本 change 不扩指标字典；golden 质量只做"歧义定死 + 分母透明"，不做用例大扩充。别名表（normalizers.py）已覆盖 7 个指标，仅按需补同义词。

### D6: 报告按运行配置归档（JSON），MD 保留"最近一次"快照

- JSON 归档：`docs/eval-reports/eval-{llm}-{platform}-{eval_date}.json`。同一配置重跑覆盖同一文件（即该配置的基线槽位）；语义层（real-mock）与端到端（real-real）天然分开，A/B 直接拿两份 JSON 走 `--compare`。
- MD 快照：`docs/eval-report.md` 保留为最近一次运行的可读快照（覆盖即可，供阅读与简历引用）。
- 理由：单一固定路径会让每次运行互相覆盖、A/B 无从比较；按配置命名让"记忆变体 / 换模型 / 换 eval_date"都只是新的归档键，无需改代码。

## Risks / Trade-offs

- [includeDebug 契约漂移：后续改动把 debug 数据漏掉或误入业务字段] → 两端契约测试钉死开/关行为；`AnalysisReport.debug` 标记为观测专用。
- [正交轴组合爆炸：4×2 组合中大量无意义组合] → CLI 校验非法组合（如 record+platform=real），只验证实际使用的 4 种。
- [mock 与真实 catalog 再次漂移] → 单数据源 + golden 指标覆盖测试；后续加指标必须改共享文件。
- [ERROR 判定误伤业务失败] → 只捕获环境异常类型，业务失败走正常判分；报告同时保留 ERROR 明细便于审计。
- [eval 负载污染运行记录（userId=eval 写入 run trace / token 统计）] → 本期接受（现有行为），后续可在 trace 层加 eval 标记（P2）。
- [21 条用例 × 多次 LLM 调用有 token 成本] → 语义层评测先行出基线；录制 cassette 后日常回归用 replay。

## Migration Plan

0. 前置清账：将 4 个已完成 change（`legacy-cleanup` / `langgraph-migration` / `semantic-resolve-node` / `agent-eval-harness`）的 delta 依次 sync 进主 specs 并归档，再开始 apply——保证 `agent-eval` 能力已存在于主 specs，本 change 归档时正确叠加。
1. P0 落地（D1 debug 透传 + D3 失败隔离 + D2 正交轴 + D6 报告归档），每步跑 `pytest` + `mvn test` 全绿。
2. 本地跑一次"语义层评测"（llm=real, platform=mock）产出第一版 L1~L4 基线。
3. P1 落地（D4 单数据源 + golden 歧义修复 + 报告分母透明）。
4. 等 MySQL 环境就绪后跑完整端到端评测（llm=real, platform=real），录制 cassette。
5. 回滚：均为小改动、无破坏性契约变化（includeDebug 默认关），可逐 commit revert。

## Resolved Questions

| 原问题 | 决定 | 落点 |
|---|---|---|
| 共享 metric catalog 文件放哪 | `src/main/resources/metric_catalog.json`（JSON，单数据源） | D4 |
| 语义层报告是否独立文件 | 不设固定双文件；JSON 按运行配置归档 + MD 最近快照 | D6 |
| 是否先 sync 主 specs | 是：apply 前先 sync + archive 4 个已完成 change | Migration Plan 第 0 步 |
