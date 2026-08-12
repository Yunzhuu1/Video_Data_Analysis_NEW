-- ============================================================
-- DataAgent 平台 DDL（统一建表入口）
-- 通过 spring.sql.init.mode=always（dev/prod）或手工执行本文件初始化。
-- DataInitializer 只负责种子数据，不再承担建表。
-- ============================================================

-- 用户维度表
CREATE TABLE IF NOT EXISTS user_dim (
    user_id VARCHAR(64) PRIMARY KEY,
    age INT,
    gender VARCHAR(16),
    region VARCHAR(32)
);

-- 时间维度表
CREATE TABLE IF NOT EXISTS time_dim (
    date DATE PRIMARY KEY,
    week INT,
    month INT,
    quarter INT,
    year INT
);

-- 创作者维度表
CREATE TABLE IF NOT EXISTS creator_dim (
    creator_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(64),
    followers INT,
    following INT,
    verified TINYINT DEFAULT 0,
    category VARCHAR(32)
);

-- 内容维度表
CREATE TABLE IF NOT EXISTS content_dim (
    content_id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255),
    description TEXT,
    tags JSON,
    duration INT,
    creator_id VARCHAR(64),
    publish_time DATETIME,
    category VARCHAR(32),
    modality VARCHAR(16),
    resolution VARCHAR(16)
);

-- 活动维度表
CREATE TABLE IF NOT EXISTS activity_dim (
    activity_id VARCHAR(64) PRIMARY KEY,
    start_time DATETIME,
    end_time DATETIME,
    type VARCHAR(32),
    target_content JSON,
    reward VARCHAR(64)
);

-- 用户行为事实表（event_type: play/like/comment/share/follow/favorite）
CREATE TABLE IF NOT EXISTS user_behavior_fact (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    timestamp DATETIME NOT NULL,
    content_id VARCHAR(64) NOT NULL,
    creator_id VARCHAR(64),
    dimension JSON COMMENT '冗余维度，如 {"category": "...", "creator_id": "..."}',
    value DOUBLE,
    INDEX idx_timestamp (timestamp),
    INDEX idx_event_type (event_type),
    INDEX idx_content (content_id)
);

-- 指标字典（语义层核心）
CREATE TABLE IF NOT EXISTS metric_definition (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    metric_name VARCHAR(128) NOT NULL,
    metric_code VARCHAR(128) NOT NULL UNIQUE,
    business_definition TEXT NOT NULL,
    formula TEXT NOT NULL COMMENT '可执行的 SELECT 表达式',
    dimensions JSON,
    time_granularity VARCHAR(32),
    source_table VARCHAR(64) COMMENT 'metric_daily / user_behavior_fact / play_detail',
    time_field VARCHAR(64) COMMENT '时间过滤字段',
    fact_formula TEXT COMMENT '明细事实表表达式（内容级/创作者级聚合用）',
    fact_event_filter VARCHAR(255) COMMENT '明细事实表事件过滤，如 event_type = ''play''',
    owner VARCHAR(64),
    version INT NOT NULL DEFAULT 1,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 每日预聚合指标表
CREATE TABLE IF NOT EXISTS metric_daily (
    date DATE NOT NULL,
    category VARCHAR(32) NOT NULL,
    total_plays BIGINT DEFAULT 0,
    total_play_duration DECIMAL(10,2) DEFAULT 0,
    total_likes BIGINT DEFAULT 0,
    total_comments BIGINT DEFAULT 0,
    total_shares BIGINT DEFAULT 0,
    total_follows BIGINT DEFAULT 0,
    total_favorites BIGINT DEFAULT 0,
    PRIMARY KEY (date, category)
) COMMENT='每日预聚合指标表';

-- 播放明细表
CREATE TABLE IF NOT EXISTS play_detail (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    content_id VARCHAR(64) NOT NULL,
    play_duration INT NOT NULL COMMENT '实际观看时长(秒)',
    drop_off_second INT COMMENT '跳出时间点(秒)：用户在视频第几秒离开',
    completion_rate DECIMAL(5,2) COMMENT '完播率',
    created_at DATETIME NOT NULL
);

-- ============================================================
-- Agent Run Trace
-- ============================================================
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

-- SQL 审计日志
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
