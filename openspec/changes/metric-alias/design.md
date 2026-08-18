## Context

指标 ID 是语义层唯一锚点（`metric_definition.metric_code`）。现状 `extract_metric_names(question, catalog)` 用**字符串包含匹配 metricName**，实测缺口：cases.yaml 9/44、synonym 22/35（hard 73%）匹配不到指标名。`metrics_consistent`（retriever.py:81）在匹配不到时返回 False → 直通被拦（c07 real-session 缺 1）、hard 层注入不可达。本 change 建立「表达 → 指标 ID」的确定性映射，并顺带验证 HITL 指标澄清叙事的数字（虚拟澄清实验）。

约束：
- 指标 ID 是权威锚点（catalog 口径/公式/来源表不变），别名/指纹只是**读取侧表达扩展**，不改写 catalog。
- `metrics_consistent` 双保险保留（别名只扩展"能判定"，不绕过 stored 一致性校验）。
- 语义路径全链路成功才沉淀（写路径门槛不变）。

## Goals / Non-Goals

**Goals:**
- 解锁 c07 类直通：real-session 7/8 → 8/8；cases 9/44 中可判定的表达映射后不再被拦。
- 产出"潜在澄清率 / 虚拟澄清收益 / 澄清率随记忆下降"三个数字，决定是否立项真 HITL。
- 零回退：--memory off N=45 不变；毒化反例仍拦。

**Non-Goals:**
- 不做 LLM 自动提炼别名（错误别名"热度"多义映射风险，候选必须全链路成功背书）。
- 不做真 HITL 指标澄清（本 change 只做虚拟澄清实验验证数字）。
- 不改指标口径/公式（catalog 权威不变）。
- 不做跨用户/多租户别名。

## Decisions

### D1：别名表（MVP，必做）
- `app/eval/aliases.yaml`：`{alias: metric_code}`，人工审核沉淀，评测驱动补充（runner 输出"匹配不到指标名清单"→ 审阅 → 入表）。
- 别名粒度：**词组级**（播放走势/播放趋势/播放表现 → total_plays），不用单字/单动词（"播放"会误匹配"播放时长"）。
- 来源：c07 类高频表达 + synonym easy 层高频表达；每个别名至少 1 个 golden/同义用例覆盖（防别名失效）。
- 理由：企业实践共识（分析师配别名）+ 改动最小（YAML + 读取扩展 ~20 行）。

### D2：读取扩展（必做）
- `extract_metric_names(question, catalog, aliases=None)`：catalog 精确名（强信号，优先级高）∪ 别名匹配（弱信号）。
- `metrics_consistent` 不变式：`found == stored` 才直通；`found` 为空仍降级 inject（双保险保留，不绕过）。
- 理由：别名只扩大"能判定"集合，不削弱防毒化（"点赞量"问题 → 精确匹配 total_likes ≠ stored total_plays → 仍拦）。

### D3：指标 ID 表达指纹（可选增强，阈值标定后启用）
- `MetricIdFingerprint.build(catalog, entries)`：catalog.metricName + 写路径沉淀的 norm_question（按 metric_codes 归属）→ 每 ID 的表达集。
- `match(question)` → 候选 ID：精确匹配 ∪ 模糊 top-1（question vs 每 ID 表达集的相似度 ≥ 指纹阈值）。
- 指纹阈值**比直通阈值宽**（如 0.6 vs hit 0.92），只做候选判定，最终仍走 metrics_consistent。
- 每 ID 表达集上限（top-20 高频），防"播放"泛化误归。
- 理由：别名覆盖高频确定性表达，指纹兜底动态表达；7 个指标规模小，指纹构建/匹配开销可忽略。
- 风险控制：指纹派生自全链路成功条目（错误映射不会进指纹）；阈值用毒化对 + 同义集标定。

### D4：虚拟澄清实验（验证 HITL 叙事，必做）
- 定义"歧义判定"：semantic resolve 低置信（confidence < 阈值）或 多指标候选（fingerprint/别名命中 ≥ 2 个 ID）。
- **golden 模拟选择**：评测中用 golden_spec 的 metrics 自动"回答"澄清（不造真 HITL 交互）。
- 产出三个数字：
  1. **潜在澄清率** = 歧义问题数 / 总问题数（无记忆基线）；
  2. **虚拟澄清收益** = 澄清后 L1 vs 不澄清 L1 的差值（说明澄清值不值得）；
  3. **澄清率随记忆下降** = 沉淀后再跑同集，歧义问题数变化（说明记忆能否自动化掉澄清）。
- 理由：成本前置问题——测"澄清率下降"需要先有澄清基线；虚拟澄清用 golden 模拟基线，半天验证叙事，再决定是否做真 HITL（真 HITL 是后续独立 change）。

### D5：评测与回归
- real-session 8/8（c07 解锁）；毒化反例 c25 仍 PASS；--memory off N=45 零回退；synonym band 分布对比（hard 层 miss → inject/hit 变化）。
- metrics-report 新增「表达映射价值」+「虚拟澄清」章节；开发日志。

## Risks / Trade-offs

- **[Risk] 别名过宽 → 误命中**（"播放"→total_plays 误匹配"播放时长"）→ 词组级别名 + catalog 精确名优先 + metrics_consistent 双保险。
- **[Risk] 指纹泛化误归** → 指纹阈值标定（毒化对全部落于阈值下）+ 每 ID 表达集上限 + 模糊只做候选不做最终判定。
- **[Risk] 冷启动指纹稀疏**（default 库 0 条）→ 指纹初始 = catalog.metricName + 评测沉淀；评测驱动增长。
- **[Risk] 虚拟澄清 ≠ 真 HITL**（golden 模拟"完美用户"）→ 数字只作为**上限参考**，报告明确标注；真 HITL 才暴露交互成本。
- **[Risk] 别名表膨胀** → 只沉淀高频（评测驱动 + 每个别名有用例覆盖）。

## Migration Plan

1. 别名表 + 读取扩展（MVP，半天）→ 单测 + 毒化/同义回归。
2. 指纹增强（阈值标定后启用，默认关闭开关控制）→ 标定脚本 + 单测。
3. 虚拟澄清实验（runner 新协议）→ 真实评测产出三个数字。
4. metrics-report + 开发日志；无部署/回滚（读取侧增强，运行时零行为变化当别名/指纹未启用时）。

## Open Questions

- 指纹阈值初始值（0.6？）→ 标定后定，标定方法见 D3。
- 歧义判定阈值（confidence < ? 算低置信）→ 虚拟澄清实验里扫描 0.5/0.7/0.9 三档。
- 虚拟澄清的"多指标候选"判定用别名+指纹还是 embedding？（倾向别名+指纹，确定性可复现）。
