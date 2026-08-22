## Why

`adversarial-system-eval` 的 P05 证明：只要保留旧的声明 hash 与 `catalogVersion`，lineage、metric definitions 或 schema projection 的实际内容被替换后，当前 `PlanValidator` 仍可能返回 PASS 并尝试进入 plan compiler，形成 3/3 unsafe pass。该问题位于受约束 Planner 的信任边界，必须在继续处理普通能力缺口前独立 fail-closed。

## What Changes

- 以项目既有 canonical JSON 算法从冻结 snapshot 的实际内容重新计算 lineage、metric、schema 三个子 hash 与组合 `catalogVersion`，不信任 snapshot 自带声明值。
- 在枚举前和 `PlanValidator` 验证最前置阶段执行完整性检查；任一声明缺失、格式非法、子 hash 或组合版本不一致时返回统一 `SNAPSHOT_INTEGRITY_MISMATCH`，禁止 plan compiler 消费该 snapshot。
- Compiler 不对校验后的外部可变 `dict` 继续取数：先复制 JSON snapshot 为私有副本，对副本校验后递归冻结，再仅从冻结副本解析 path/binding/edge/metric，关闭“校验后修改原对象”的 TOCTOU。
- 保持请求级兼容路径：完整性失败的 snapshot 不参与计划驱动编译，可按现有图路由进入不读取该 snapshot 的 legacy synthesizer，并继续经过 SQL Guard；不把安全回退伪装为计划验证成功。
- 将 P05 lineage/metric/schema 三个 variants 从“已知 unsafe pass”升级为确定性回归门槛，目标 unsafe pass `3/3 → 0/3`，并覆盖缺失 hash、只改组合版本、合法 snapshot、验证顺序与 `REJECT → legacy fallback → SQL Guard` 图路径。
- 仅修复快照完整性 P1；不顺带修改 Guard/query-shape、未知指标、prompt injection 或 Planner 重试策略。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `lineage-aware-planning`：计划枚举与验证增加对冻结 snapshot 实际内容的四 hash 完整性校验，漂移时禁止计划编译并安全回退。
- `adversarial-system-eval`：P05 三组件漂移从条件式暴露 unsafe pass 改为必须由真实生产 Validator 全部拒绝的回归契约。

## Impact

- Python：`agent-engine/app/lineage/catalog.py`、`planning.py`，必要的 graph 观测/回退 reason；不新增第三方依赖。
- 评测：复用 `adversarial_cases.json` 的 P05 三 variants、offline/integrated 报告和 lineage offline 门槛。
- API/数据库：无外部 API、Schema 或数据迁移；Spring 仍负责发布冻结 snapshot，Python 在消费端增加独立防御。
- 兼容性：合法 snapshot 的 planId、SQL 与主链路行为不变；非法 snapshot 不再进入 plan compiler。
