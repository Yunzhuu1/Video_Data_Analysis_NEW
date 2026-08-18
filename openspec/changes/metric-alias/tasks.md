## 1. 别名表 + 读取扩展（MVP）

- [ ] 1.1 新增 `app/eval/aliases.yaml`（词组级别名：播放走势/播放趋势/播放表现/观看量/完播情况/点赞数等 → 指标 ID），每个别名标注覆盖用例
- [ ] 1.2 `extract_metric_names` / `metrics_consistent` 接别名表（catalog 精确名优先，别名弱信号；**最长匹配优先**防「播放走势」被「播放」错配；found==stored 不变式保留）
- [ ] 1.3 单测：别名命中/别名与 stored 不一致仍拦/别名不覆盖 catalog 精确名/匹配不到仍降级 inject

## 2. 指标 ID 表达指纹（可选增强）

- [ ] 2.1 `MetricIdFingerprint`：从 catalog.metricName + 写路径沉淀 norm_question（按 metric_codes 归属）构建每 ID 表达集（上限 top-20）
- [ ] 2.2 阈值标定：`calibrate_fingerprint.py`——**相似度定义写死（复用混合检索融合分，或 embedding cosine + 单独标定，二选一）**；毒化对全部落于阈值下 + 同义集期望映射全部落于阈值上；默认开关关闭（`MEMORY_ALIAS_FINGERPRINT=0`）
- [ ] 2.3 单测：指纹构建/匹配/泛化防御（"播放"不误归 total_plays vs total_plays_time）

## 3. 虚拟澄清实验

- [ ] 3.1 歧义判定：低置信（confidence 阈值扫描 0.5/0.7/0.9）+ 多指标候选（别名/指纹命中 ≥2 个 ID）
- [ ] 3.2 runner 虚拟澄清协议：golden 自动模拟选择，产出潜在澄清率（**拆歧义且错/歧义但对**）/ 虚拟澄清收益（澄清后 L1 差，主指标）/ 澄清率随沉淀下降（**按 band 分层，只统计 hit/inject 可达项，miss 单独报记忆不可达**）
- [ ] 3.3 单测：构造歧义/非歧义用例断言三数字；报告标注"golden 模拟完美用户，上限参考"

## 4. 评测与回归

- [ ] 4.1 Python pytest + ruff 全绿
- [ ] 4.2 `--memory off` N=45 回归零回退
- [ ] 4.3 real-session 重跑：7/8 → 8/8（c07 解锁，目标口径=9/44 中 5 个可判定用例被表达映射解锁的 N 个）；毒化反例 c25 仍 PASS
- [ ] 4.4 synonym band 分布对比（hard 层 miss → inject/hit 变化）+ alias_hit 报告
- [ ] 4.5 metrics-report 新增「表达映射价值」+「虚拟澄清」章节；开发日志追加

## 5. 收尾

- [ ] 5.1 全量终验（pytest + ruff）；提交并推送分支
