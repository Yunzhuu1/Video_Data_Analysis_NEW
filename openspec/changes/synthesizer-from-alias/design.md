## Context

真实评测（2026-08-13）观测修复后 Source 列全部 `fallback`。定位到根因（BUG-006）：`sql_synthesizer.py` 用 `_ALIAS` 映射（如 `metric_daily→md`）生成列引用（`md.category`）和 FROM 子句，但 FROM 只输出别名本身（`FROM md`），未声明 `FROM metric_daily md`。MySQL 报 `Table 'md' doesn't exist` → `SQL_EXECUTE`/`SQL_VALIDATE` 失败 → `route_after_validate` 路由回 `SQL_GENERATE` → `sql_generate_node` 把 `sql_source` 覆盖为 `fallback`。

```text
synthesize(): SELECT md.category, SUM(total_plays) FROM md GROUP BY md.category
                                                              ^^^ 缺表名
→ MySQL: Table 'video_data_analysis.md' doesn't exist
→ 降级 raw LLM → sql_source=fallback（覆盖 semantic）
```

## Goals / Non-Goals

**Goals:**
- 合成 SQL 在真实 MySQL 上可执行：FROM 子句输出 `FROM {source} {alias}`。
- 全 source 分支与 JOIN 场景统一（metric_daily / user_behavior_fact / play_detail）。
- 单元测试覆盖可执行性（真实表名 + 别名声明）。
- 真实评测 Source 列出现 `semantic`（可选验收）。

**Non-Goals:**
- 护栏误报/漏报、dimensions 抽取、多指标合成、SQL 优化器调优。

## Decisions

### D1: FROM 子句统一为 `FROM {source} {alias}`
`_ALIAS.get(source, source)` 已提供别名；修复点集中在 FROM 子句与 detail 分支：
- 聚合/趋势/排名：`FROM {alias}` → `FROM {source} {alias}`
- detail：`SELECT * FROM {alias}` → `SELECT * FROM {source} {alias}`
- JOIN 场景：`_field_expr` 已返回 join 子句（基于别名），保持不动；仅 FROM 需要真实表名。
- 备选：去掉别名直接用真实表名 → 拒绝：join/列引用已按别名编写，改动面更大且可读性差。

### D2: 可执行性测试
新增测试断言：合成 SQL 含 `FROM metric_daily md` 形态（真实表名 + 别名），并对每个 source 分支（含 join 的 user_behavior_fact）覆盖。真实 MySQL 执行验证放手动/评测重跑（测试套件不依赖 DB，保持 hermetic）。

## Risks / Trade-offs

- [改 FROM 后 mock 测试的 `FROM md` 断言失效] → 同步更新 `test_semantic_path` 断言为 `FROM metric_daily md`。
- [真实评测重跑耗时 ~20 分钟] → 单元测试先行，真实重跑作为可选验收。
- [detail/JOIN 分支遗漏] → 测试覆盖三张 source 表路径。

## Migration Plan

1. 修 `synthesize()` FROM 子句（聚合/趋势/排名 + detail）。
2. 更新/新增单元测试（含真实表名断言）。
3. pytest + ruff 全绿。
4. 可选：重跑真实评测验证 Source 列出现 semantic。

## Open Questions

- 合成 SQL 若在真实库执行仍失败（如 guard 规则），是否继续降级 raw LLM？→ 维持现状（降级是特性，不是 bug），本 change 只保证合成 SQL 本身可执行。
