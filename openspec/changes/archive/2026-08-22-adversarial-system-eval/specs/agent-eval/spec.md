## ADDED Requirements

### Requirement: 多协议对抗评测调度
既有评测 runner SHALL 支持从独立 adversarial manifest 调度 question、fixed intent、mutated plan/snapshot 与 raw SQL/fault injection，并将各 adapter 的 observation 归一为 observation_status、可选 disposition、stage/code/node trace/audit/result 结构；非OK observation不得填写或进入系统 disposition 统计，普通 N=61 runner 行为 SHALL 保持不变。

#### Scenario: 对抗协议统一执行
- **WHEN** 使用 adversarial CLI 运行指定 profile
- **THEN** runner 按 case protocol 调用对应 adapter，输出20条逐例 observation 和按层聚合，不将 adapter 异常静默吞为产品失败

#### Scenario: Observation与系统处置正交
- **WHEN** adapter环境不可用、执行异常、profile不适用或comparator无法分类
- **THEN** runner填写对应observation_status且disposition为空；只有status=OK时才聚合六类系统处置

#### Scenario: 普通评测零行为回退
- **WHEN** 使用既有参数运行 N=61 replay/mock 回归
- **THEN** 用例选择、L1-L4、R1、sql_source 和状态路由与引入 adversarial runner 前一致，对抗字段不改变既有分母

### Requirement: 对抗审计完整性比较器
评测比较器 SHALL 按 case layer 校验 required audit fields、must-visit/must-not-visit nodes、selected plan/catalog version/fallback reason/approval SQL hash 等相关证据，并将缺失字段与处置不符分开报告。

#### Scenario: 按层检查审计机会数
- **WHEN** 汇总 Semantic、Planning、Synthesis、Safety/Recovery observations
- **THEN** 每层仅以其 required audit fields 的实际机会数为分母，分别输出完整数/总数和缺失字段明细

#### Scenario: 处置错误与审计缺失分离
- **WHEN** 某 case 的 disposition 符合 expected 但缺少 required audit field
- **THEN** Expected Disposition 可通过但 Audit Completeness 失败，报告不得合并为一个模糊错误

#### Scenario: 合成失败原因进入真实Graph观测
- **WHEN** 确定性合成器抛出SynthesisError并按既有行为降级raw SQL
- **THEN** graph state、Run Trace与includeDebug观测均包含generic synthesis_error_code和原始synthesis_error_reason；新增字段不得改变semantic_ok、路由、SQL生成或门禁行为

#### Scenario: 函数调用不冒充图节点
- **WHEN** 对抗fixture需要验证SQL_SYNTHESIZE节点内部的plan compiler是否被调用
- **THEN** observation以compiler_invocation_attempted和参数hash记录函数调用尝试，不得虚构PLAN_COMPILER节点或因sentinel阻断而报告为从未尝试

### Requirement: 对抗运行日志与中断终结
对抗runner SHALL 在profile进入STARTED前以稳定`case_id`或`case_id::variant_id`构造唯一execution-unit registry，原子持久化完整ledger与锁定分母，并以unit ID为幂等键逐条原子写terminal observation；runner SHALL 提供可重复调用的finalizer，使正常异常、超时和进程被杀后均能生成每个expected unit恰好一条terminal record的COMPLETED或ABORTED终态报告。

#### Scenario: STARTED事务边界持久化
- **WHEN** profile preflight通过准备执行case
- **THEN** runner先原子写run ID、manifest/config hash、key唯一的execution-unit registry、锁定分母、process identity、lease和全部PENDING状态，成功后才将profile标记STARTED；重复unit ID在STARTED前fail-fast

#### Scenario: Finalizer幂等
- **WHEN** 对同一COMPLETED或ABORTED run多次调用finalizer
- **THEN** terminal record数量、每条record hash、结果文件hash和锁定分母完全不变，不新增重复record、不覆盖真实terminal observation；任何existing duplicate不得通过幂等路径被静默去重

#### Scenario: Execution unit严格一一对应
- **WHEN** finalizer或reporter读取冻结registry与terminal records
- **THEN** 同时校验registry/record基数相等、每个expected unit出现次数恰为1、missing/duplicate/unknown/orphan均为0；任一失败直接Harness FAIL且禁止产品指标聚合
