## Context

合成器 v1 docstring 声称"相对时间由解析器已展开为 absolute"，但 semantic_resolver 与合成器均未实现——`time_range.type == "relative"` 时合成 SQL **无时间过滤**。R1 实测抓到 c03「最近7天每天播放量是多少」返回全 31 天；影响面 11 个 relative 用例中 9 个无过滤（c03/c13/n04/n09/n10/n11/n22/n23/n25）。数据范围 2023-10-01 ~ 2023-10-31（seed 42 确定性）。

约束：
- Python 不直连业务库（SQL 执行走 Spring SQL 网关）。
- L1-L4 的 time_range 与 golden 的 relative 比对，展开不改意图层判定。
- seed 42 数据确定性 → 锚点（数据末日）稳定，R1 可复现。

## Goals / Non-Goals

**Goals:**
- relative → absolute 确定性展开，c03 类合成 SQL 含 `WHERE date BETWEEN ...`。
- R1 扩展到 relative 用例并验证修复（12 → 含 relative 用例，目标全绿）。
- --memory off N=45 零回退。

**Non-Goals:**
- 不做自然语言时间语义增强（"上个月/去年同期"等复杂表达——LLM 解析层的事）。
- 不改合成器 absolute 逻辑（已支持）。
- 不做多时区/营业日历。

## Decisions

### D1：time_expand 纯函数（确定性）
```python
def time_expand(relative: dict, anchor_date: str) -> dict:
    """{amount, unit} + 数据末日 → {type: "absolute", start, end, granularity}"""
    amount = int(relative["amount"])
    unit = str(relative.get("unit") or "day")
    days = {"day": 1, "week": 7, "month": 30}[unit] * amount  # month 近似 30 天
    end = anchor_date
    start = anchor_date - (days - 1)  # 含端点：最近7天 = [anchor-6, anchor]
    return {"type": "absolute", "start": start, "end": end, "granularity": relative.get("granularity")}
```
- 含端点语义：`最近7天` = 末日往前 6 天（共 7 天），与 seed 42 模式（10/1-7 激增）对齐可验证。
- 理由：数据末日锚点 + 含端点，确定性最强，R1 可复现。

### D2：锚点来源（数据末日）
- nodes 在合成前，若 intent.time_range 为 relative：
  - real：调 `platform.execute_sql("SELECT MAX(<timeField>) FROM <source>")`（走 Spring SQL 网关，符合"Python 不直连库"）。
  - mock：platform 返回固定锚点 `2023-10-31`（与 seed 42 数据末日一致，测试可复现）。
- timeField/source 从 metric_defs 取（如 metric_daily.date / play_detail.created_at）。
- 理由：锚点 = 数据末日（而非系统当前日期），与 seed 42 数据确定性一致；当前日期会随运行漂移破坏 R1 复现。

### D3：展开位置
- 在 `semantic_resolve_node` 之后、`sql_synthesize_node` 之前，nodes 增加展开步骤（同步函数 `_expand_relative_time(state)`）：
  - 仅当 `time_range.type == "relative"` 时查询锚点并替换为 absolute。
  - 查询失败 → 保持 relative（合成器现状，降级不打断主链路）。
- 理由：展开是语义层修正（"最近7天"的绝对区间），合成器保持纯函数（不注入数据依赖）。

### D4：R1 闭环验证
- 修复后为 relative 用例取真值（独立手工 SQL，锚点=数据末日）并标 expected_result。
- R1 评测：c03/c13 等合成 SQL 应含 `WHERE date BETWEEN '2023-10-25' AND '2023-10-31'`，结果与真值一致 → R1 扩展到 relative 用例全绿。
- 交叉诊断：修复前这些用例是"L1 对 + R1 错（value_mismatch）"候选，修复后归入通过——**R1 驱动修复闭环的完整证据**。

### D5：边界
- unit 支持 day/week（month 近似 30 天，标注）。
- "昨天到今天" = amount=2 day（含端点）。
- "最近一周" = amount=7 day。

## Risks / Trade-offs

- **[Risk] 锚点=数据末日 vs 业务语义"今天"**（真实系统里用户问"最近7天"应该以今天为锚）→ 当前数据是历史快照（末日 10-31），用数据末日使 R1 可复现；真实部署时锚点应切系统日期（Open Question，本 change 用数据末日保证评测确定性）。
- **[Risk] 展开失败静默降级**（查询锚点失败 → relative 保持 → 又无过滤）→ 记录 warning，R1 会标 value_mismatch 暴露（不静默）。
- **[Risk] month 近似 30 天** → 标注边界；seed 42 用例无 month 需求。
- **[Risk] mock/real 锚点不一致** → mock 固定 2023-10-31 与 seed 42 一致，测试与真实同构。

## Migration Plan

1. time_expand 纯函数 + 单测。
2. nodes 展开集成（含 platform 查询锚点 + mock 固定锚点）。
3. relative 用例取真值 + R1 扩展 + 单测。
4. --memory off N=45 回归 + R1 评测（relative 全绿）。
5. metrics-report + 开发日志；Java 无改动。

## Open Questions

- 锚点：数据末日（本 change，R1 可复现）vs 系统当前日期（真实语义）→ MVP 数据末日，真实部署切换点记录。
- unit 范围：day/week 够用，month 近似 30 天是否接受 → 标注边界。
- 查询锚点的 platform 接口形态：复用 execute_sql 还是新只读端点 → 倾向复用 execute_sql（SELECT MAX 低风险）。
