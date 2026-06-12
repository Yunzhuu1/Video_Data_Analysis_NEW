-- 播放明细表：记录每次播放的详细体验数据
-- 加入后，RAGAgent 的评论证据可以被客观数据验证
CREATE TABLE IF NOT EXISTS play_detail (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    content_id VARCHAR(64) NOT NULL,
    play_duration INT NOT NULL COMMENT '实际观看时长(秒)',
    drop_off_second INT COMMENT '跳出时间点(秒)：用户在视频第几秒离开',
    completion_rate DECIMAL(5,2) COMMENT '完播率',
    created_at DATETIME NOT NULL
);

-- 拓展内容表字段（用于交叉验证"广告太多"类评论）
ALTER TABLE content_dim ADD COLUMN IF NOT EXISTS ad_count INT DEFAULT 0 COMMENT '贴片广告数量';
ALTER TABLE content_dim ADD COLUMN IF NOT EXISTS ad_positions JSON COMMENT '广告插入时间点';

-- Agent Run Trace: 记录每次分析请求的顶层生命周期
CREATE TABLE IF NOT EXISTS agent_run (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL UNIQUE,
    user_id VARCHAR(64) NOT NULL,
    question TEXT NOT NULL,
    status VARCHAR(32) NOT NULL,
    current_node VARCHAR(64),
    final_report LONGTEXT,
    error_message TEXT,
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    total_duration_ms BIGINT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_created (user_id, created_at),
    INDEX idx_status_created (status, created_at)
);

-- Agent Run Node Trace: 记录每个 Agent 节点的输入、输出、耗时和错误
CREATE TABLE IF NOT EXISTS agent_run_node (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    node_name VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    input_payload MEDIUMTEXT,
    output_payload MEDIUMTEXT,
    error_message TEXT,
    model_name VARCHAR(128),
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    duration_ms BIGINT,
    retry_count INT DEFAULT 0,
    started_at DATETIME,
    finished_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run_id (run_id),
    INDEX idx_node_status (node_name, status),
    INDEX idx_created_at (created_at)
);

-- SQL 审计日志：记录 Agent 生成 SQL 的访问资产、风险和执行决策
CREATE TABLE IF NOT EXISTS agent_audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64),
    user_id VARCHAR(64),
    action VARCHAR(64) NOT NULL,
    sql_text TEXT,
    accessed_tables VARCHAR(512),
    accessed_columns TEXT,
    risk_level VARCHAR(32),
    decision VARCHAR(32),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run_id (run_id),
    INDEX idx_user_created (user_id, created_at)
);
