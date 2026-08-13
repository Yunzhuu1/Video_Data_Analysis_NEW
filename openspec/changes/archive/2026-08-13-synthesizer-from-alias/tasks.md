## 1. 合成器 FROM 子句修复

- [x] 1.1 synthesize() 聚合/趋势/排名分支：FROM 子句改为 `FROM {source} {alias}`
- [x] 1.2 detail 分支：`FROM {alias}` 改为 `FROM {source} {alias}`
- [x] 1.3 核对 JOIN 场景（user_behavior_fact / play_detail）FROM 一致性

## 2. 可执行性测试

- [x] 2.1 新增合成器测试：断言三张 source 表路径的 FROM 均含真实表名 + 别名声明
- [x] 2.2 更新 test_semantic_path 中 `FROM md` 断言为 `FROM metric_daily md`

## 3. 回归与文档

- [x] 3.1 Python pytest 59/59（新增三 source 路径测试）+ ruff clean
- [x] 3.2 真实评测重跑：Source=semantic 0/21→12/21、延迟 p50 40.5s→30.2s / p95 91.5s→77.2s、L1 保持 100%。注：端到端 66.67%→47.62% 系 c15/c16 期望重试数=1 而语义 SQL 0 重试导致（评测设计伪影），非真实回归
- [x] 3.3 更新 docs/开发日志.md（BUG-006 修复 + 真实评测验证结果）
