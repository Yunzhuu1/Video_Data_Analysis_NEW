## ADDED Requirements

### Requirement: 记忆评测自隔离
评测 SHALL 通过 eval namespace 实现记忆自隔离：`--memory on` 使用独立 eval namespace（per-eval，如 `eval-<eval_date>-<start_ts>`），启动时清空该 namespace，反例预置写入该 namespace；真实记忆（default namespace）SHALL 不受评测影响。

#### Scenario: eval namespace 自隔离
- **WHEN** 运行 `--memory on` 评测
- **THEN** 评测使用独立 eval namespace（per-eval，一次评测一个），无需服务端 `MEMORY_DB_PATH` 切换或手动删库；评测前后 default namespace 条目不变

#### Scenario: 反例真预置（毒化变体）
- **WHEN** 运行相似反例用例（real 模式）
- **THEN** 预置"毒化变体"（问题文本与 intent 指标不一致）通过 `POST /internal/memory/seed` 写入 eval namespace（服务器 store）；查询同文本（相似度 ≥ 直通阈值）时 metrics 一致性校验拦截，band != hit
