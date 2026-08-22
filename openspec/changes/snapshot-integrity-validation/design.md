## Context

当前 Spring 发布的 lineage snapshot 同时包含四个声明值：`lineageHash`、`metricCatalogHash`、`schemaHash`、组合 `catalogVersion`，以及对应实际内容 `lineage`、`metricDefinitions`、`schemaProjection`。Java/Python 已共享受限 canonical JSON 规则并有固定 fixture，但 Python `PlanValidator` 目前只比较 `plan.catalogVersion == snapshot.catalogVersion`，没有证明声明值确实由当前内容计算而来。

P05 分别修改三类内容并保留全部旧声明值，真实 Validator 三次均 PASS；harness 的独立 oracle 检出漂移，compiler sentinel 才阻断调用。这说明“版本字段存在”不等于“版本与内容绑定”。该漏洞位于合法计划进入 compiler 前的确定性信任边界，适合做独立小 hotfix，不需要 LLM、embedding 或新基础设施。

## Goals / Non-Goals

**Goals:**

- 从 snapshot 实际内容独立重算三个子 hash 与组合 `catalogVersion`，拒绝缺失、非法或不一致声明。
- 在枚举、Validator 和 compiler 三个边界实施同一完整性算法；Compiler 只消费经复制、校验并递归冻结的私有副本，关闭验证后篡改的 TOCTOU 窗口。
- 完整性失败使用稳定 code `SNAPSHOT_INTEGRITY_MISMATCH` 和确定顺序的 component diagnostics；禁止 plan compiler 消费失配 snapshot。
- 把不可由“换一个候选”恢复的完整性错误与普通 `REPLAN` 分开，不浪费 Planner 重试。
- 保持合法 snapshot 的 candidate/planId/SQL 完全不变，并复用 P05 将 unsafe pass 3/3 降为 0/3。

**Non-Goals:**

- 不引入图数据库、签名/KMS、远端 attestation 或 snapshot 持久化服务。
- 不修复 C02-C04 Guard/query-shape、S04 未知指标、S05 prompt injection 等 P2。
- 不改变 canonical JSON profile、Spring snapshot 生成算法、Planner 选择策略或最大重试次数。
- 不把旧的失败评测报告改写成绿色；hotfix 产生新的 run 证据。

## Decisions

### D1. 以实际内容为唯一重算输入，四个声明值全部验证

新增无副作用完整性函数，输入当前内存中的 snapshot，按固定映射重算：

```text
actual_lineage_hash = sha256(canonical(snapshot.lineage))
actual_metric_hash  = sha256(canonical(snapshot.metricDefinitions))
actual_schema_hash  = sha256(canonical(snapshot.schemaProjection))

actual_catalog_version = sha256(canonical({
  "lineage": snapshot.lineage,
  "metrics": snapshot.metricDefinitions,
  "schema":  snapshot.schemaProjection
}))
```

按 `lineage → metric → schema → catalog` 固定顺序比较 `lineageHash / metricCatalogHash / schemaHash / catalogVersion`。任一内容或声明缺失、声明不是 64 位小写 hex、canonicalization 失败或值不一致，都返回 `valid=false`、统一 code 和 `mismatchedComponents`；审计可记录 declared/actual hash，但不得记录完整 catalog 内容。

选择复用 `catalog.py` 的 `canonical_hash`，而不是：

- 重新读取 Git 资源：真实模式的权威输入是本轮冻结 snapshot，重读文件会引入第二份状态和竞态；
- 只重算组合版本：无法给出哪个组件漂移的可审计证据；
- 只比较三个子 hash：攻击者也可只替换组合 `catalogVersion`。

### D2. 三道相同校验，Validator 是规范决策点

1. `PlanEnumerator.enumerate()` 开始前校验，避免从失配内容生成候选；失败抛出专用 `SnapshotIntegrityError`，`plan_enumerate_node` 记录 `REJECT/SNAPSHOT_INTEGRITY_MISMATCH`、零候选和 legacy fallback。
2. `PlanValidator.validate()` 在 selected ID membership、candidate canonical re-enumeration之前校验。失败返回 `verdict=REJECT`，不得被 `INVALID_PLAN_ID` 或 `CANDIDATE_TAMPERED` 覆盖真实根因。
3. `synthesize_plan()` 不在原始可变 dict 上执行“校验后继续读取”。入口先用 canonical JSON round-trip 复制出仅由 JSON 值组成、无外部引用的私有副本；在该副本上执行完整性校验，通过后把 dict/list 递归转换为只读 mapping/tuple，Compiler 后续只持有并读取这份冻结对象。原始 snapshot 在复制前已漂移会使副本校验失败；复制后再漂移不会影响编译输入。失败转换为现有可观测的 `SynthesisError`，不得生成部分 SQL。

三处必须调用同一个 helper，不复制 hash 公式。冻结函数只接受通过 JSON canonicalization 的 payload，不保留指向原 snapshot 的嵌套引用，也不向调用方暴露可变内部对象。合法 snapshot 重复计算成本仅为小型 JSON 的 SHA-256，远低于一次 LLM/数据库调用；MVP 不做缓存，避免缓存键再次成为可伪造声明。

### D3. 完整性错误不重选候选，但允许请求走不读取该 snapshot 的 legacy 路径

新增计划层 verdict `REJECT`：表示本轮 snapshot 整体不可信，不是候选 ID 选择错误。

- `REPLAN`：候选级错误，可按既有策略重选一次；
- `REJECT/SNAPSHOT_INTEGRITY_MISMATCH`：不进入 `PLAN_SELECT`，不增加 planning retry，设置 `legacyPlannerFallback=true`；`plan_validate_node` 若收到 Enumerator 已记录的 REJECT 必须原样保留，不得用 `NO_CANDIDATE` 覆盖；
- plan compiler 仅接受 PASS；legacy synthesizer 不消费 `lineage_snapshot`，生成 SQL 后仍必须经过统一 Guard。

这里的 `SAFE_REJECT` 是“拒绝不可信语义计划”，不是强制整个自然语言请求返回错误。与直接中断相比，保留 legacy 路径能维持现有可用性；与继续 REPLAN 相比，它不会在同一坏 snapshot 上做无意义重试。debug/trace 必须保留 integrity code 和 mismatch components，不能把回退写成普通无候选。

图级回归必须使用失配 snapshot 的 fake platform 和 Planner/plan-compiler spies，证明有序轨迹为 `PLAN_ENUMERATE → PLAN_VALIDATE(REJECT) → SQL_SYNTHESIZE(legacy) → SQL_HARD_GUARD`；`PLAN_SELECT` 调用数、planning retry 与 plan compiler 调用数均为 0。测试不得只调用 helper 或手工拼一个最终 state。

### D4. P05 从发现型 case 升级为 hotfix 门槛

保持 P05 fixture 的攻击方式不变：分别修改 lineage、metric definitions、schema projection，故意保留旧四个声明值。修改后的真实期望为：

```text
3/3 observation_status = OK
3/3 disposition = SAFE_REJECT（计划级）
3/3 code = SNAPSHOT_INTEGRITY_MISMATCH
3/3 compiler_invocation_attempted = false
0/3 unsafe_pass
variant coverage = 3/3
```

另补四类单测：合法 snapshot PASS；只改声明值拒绝；缺失/非法 hash 拒绝；Validator PASS 后再篡改原 snapshot 时，Compiler 使用其入口创建的私有冻结副本且不再读取原对象。再增加并发 mutation fixture：冻结完成后修改原 snapshot，输出 SQL 必须与未修改基线一致；冻结前已漂移则必须拒绝。旧 adversarial 报告保持不可变，新报告使用新 run 目录。

### D5. 回归范围按确定性证据收敛

本 hotfix 不需要真实 LLM/embedding。完成门槛：

- snapshot integrity + PlanValidator + graph fallback + compiler sentinel 定向测试；
- adversarial offline P05 三 variants 全拒绝、unsafe 0/3；
- lineage offline 原有 Path Recall 8/8、选择/拒绝门槛不回退；
- N=61 replay/mock 实现前后 behavior projection 一致；
- 全量 Python、Java、ruff 与 OpenSpec strict 通过。

## Risks / Trade-offs

- **[合法跨版本部署被识别为 mismatch]** → 这是预期 fail-closed；必须由 Spring 在单次冻结时同步生成内容和四个声明值，不能拼接不同版本 payload。
- **[三次 canonical hash 有重复 CPU]** → 当前 catalog 很小且纯本地，优先安全与简单；只有 profiling 证明成本显著后才考虑以不可伪造的对象封装缓存。
- **[legacy fallback 掩盖规划不可用]** → `planValidation.code`、warning、legacy flag 与 mismatch components 必须保留，评测单独统计；业务 SQL 仍过 Guard。
- **[冻结结构与现有 Compiler 的 dict/list 假设不兼容]** → 只使用支持 `[]`、`.get()` 与迭代的只读 Mapping/tuple，并为全部 path/binding/edge/filter/order 分支跑既有 compiler 测试。
- **[compiler 直接调用异常类型改变]** → 统一转换为既有 `SynthesisError`，保留原降级路由和观测 code/reason。
- **[只防内容完整性，不防可信发布端主动伪造全部内容与 hash]** → 本 change 的威胁模型是传输/缓存/内存漂移和版本拼装错误；签名与远端身份认证属于后续基础设施治理。

## Migration Plan

1. 先实现共享 integrity result/error 与合法/非法 fixture 测试。
2. 接入 Enumerator、Validator、Compiler 私有冻结副本三个边界和 graph `REJECT` 路由语义。
3. 重跑 P05 与 lineage/N=61/full regression，生成新的 hotfix 报告并更新开发日志/面试素材。
4. 无数据迁移；回滚可恢复上一版代码。若出现兼容问题，临时关闭 lineage planning 仍可使用 legacy 主链路，但不得删除失败证据或放宽 expected。

## Open Questions

无。MVP 明确采用 Python 消费端三道校验、计划级 REJECT + 请求级 legacy fallback，不引入签名服务。
