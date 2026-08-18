## Why

评测严谨性受限于样本：golden cases 仅 25 个（简历报"N=25 的 96%"说服力弱），同义集 20 条**全部是"易层"改写**——exp2 实测组 A（无记忆）L1=100%，导致注入增益恒为 0、无法量化。目标：**扩大样本（N=25→45）让基线可信，并构造"难层"改写让 few-shot 注入的价值显形**（注入增益 >0 可量化）——同时服务简历数据与评测严谨性。

## What Changes

- **golden cases 扩展**：`app/eval/cases.yaml` 25 → ~45，新增 20 条覆盖：
  - 多指标组合（播放量+点赞量同查）、多条件过滤（分类+时间+指标）
  - 排名+时间嵌套（"美食类近30天完播率最高的前5个视频"）
  - 跨表 JOIN（creator/content/play_detail 维度）、长尾/歧义难例
  - 每条含 `golden_spec`（可判定）；新增用例先过真实 LLM 探测再定稿（根因基线打法）
- **同义集扩展 + 难度分层**：`app/eval/synonym_cases.yaml` 20 → ~35，新增 15 条**难层**改写（`difficulty: hard`）：
  - 冷门指标叫法（"完播表现"→completion_rate）、间接说法（"点赞互动最活跃"→engagement_rate）
  - 歧义陷阱（"最近7天看的人有多少"）、长尾复杂结构、业务黑话
  - **客观筛选标准**：难层条目以"组 A（无记忆）实测 L1<100%"为准（先构造候选 → 真实筛选出真错项），不拍脑袋标难
- **runner 小适配**：difficulty 字段透传；新增难层筛选脚本（组 A 跑同义集 → 标出真错项）；实验报告按难度分层（easy/hard 分开报 L1 与注入增益）
- **产出**：N=45 的 L1-L4 基线（更大样本可信数字）+ **难层注入收益报告**（注入增益首次可能 >0，完成记忆故事最后一环）

## Capabilities

### New Capabilities
<!-- 无：评测数据与难层实验归属既有 agent-eval -->

### Modified Capabilities
- `agent-eval`: 「量化指标测量」增加**难层改写**场景（difficulty 分层 + 组 A 实测筛选 + 按难度报告注入收益）；「评测数据」覆盖度契约（golden cases 须覆盖多指标/多条件/跨表/长尾难例）

## Impact

- **Python**：`app/eval/cases.yaml`（+20 golden）、`app/eval/synonym_cases.yaml`（+15 难层，difficulty 字段）；`app/eval/runner.py`（difficulty 透传 + 按难度分层报告）；新增 `app/eval/hard_layer_filter.py`（难层筛选脚本）；`app/eval/calibrate_thresholds.py` 或实验入口兼容 difficulty；`tests/`（新用例 golden 覆盖校验、难层筛选脚本可复现）。
- **Java**：无改动（评测数据在 Python 侧）。
- **数据库/架构**：**零改动**（纯评测数据 + runner 适配）。
- **评测**：新增用例先真实 LLM 探测定稿；N=45 全量跑（--memory off 回归 + --memory on 难层注入实验，~15-25 分钟）；报告更新。
- **文档**：`docs/metrics-report.md`（N=45 基线 + 难度分层注入收益）；`docs/开发日志.md` 新条目。
