## 1. 数据模型扩展

- [x] 1.1 schema.sql 新增 4 表（creator_revenue/video_revenue/user_retention/content_quality）DDL
- [x] 1.2 DataInitializer 灌新表数据：seed 42 确定性 + 真实业务模式（长尾 80/20、稀疏分类、异常峰值/断档；节日效应复用既有 10/1-7 模式，可选 10/10 返场）
- [x] 1.3 TableSchemaRegistry 注册 4 新表（表类型 FACT/DIM）+ 敏感列评估
- [x] 1.4 数据放大：**既有 2023-10 数据字节级不变**（旧 R1 真值稳定），放大通过新增日期区间（2023-11/12）与新表实现（seed 42 复现）

## 2. 指标与别名

- [x] 2.1 metric_catalog.json 新增 8 指标（comment_rate/like_rate/share_rate/avg_completion_ratio/creator_revenue/video_revenue/active_creator_count/daily_active_users）
- [x] 2.2 aliases.yaml 补新指标用户说法映射

## 3. 评测扩展

- [x] 3.1 cases.yaml 新增 ~25 用例（新指标/新表/新关系/真实分布），标 golden_spec
- [x] 3.2 新用例用独立手工 SQL 取 R1 真值（expected_result + truth_source）
- [x] 3.3 全量 pytest（Python 主链路零改动应全绿）+ ruff；**合成器单测补比率/去重指标**（防静默错误 SQL，P2-1/P2-2）

## 4. 评测与基线

- [x] 4.1 --memory off 新基线评测（N=~70）：既有 45 例子集 L1-L4/R1 零回退 + 新增 ~25 例独立报告
- [x] 4.2 R1 全量（新旧用例）验证；合成器对新表/新指标查询不报未捕获错误（已知边界标 fallback）
- [x] 4.3 metrics-report 更新（新基线 + 新指标/表）+ 开发日志

## 5. 收尾

- [x] 5.1 全量终验（pytest + ruff）；提交并推送分支
