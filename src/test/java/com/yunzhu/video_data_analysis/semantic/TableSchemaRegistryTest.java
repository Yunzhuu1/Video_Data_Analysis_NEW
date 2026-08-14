package com.yunzhu.video_data_analysis.semantic;

import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class TableSchemaRegistryTest {

    @Test
    void parsesSimpleCreateTable() {
        String sql = """
                -- 测试表
                CREATE TABLE IF NOT EXISTS test_tbl (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(64) NOT NULL,
                    amount DECIMAL(10,2) DEFAULT 0,
                    INDEX idx_name (name)
                );
                """;
        var registry = new TableSchemaRegistry(sql);

        assertThat(registry.hasTable("test_tbl")).isTrue();
        assertThat(registry.columnsOf("test_tbl")).containsExactlyInAnyOrder("id", "name", "amount");
    }

    @Test
    void handlesCommentWithCommaAndEscapedQuote() {
        String sql = """
                CREATE TABLE IF NOT EXISTS fact_tbl (
                    id BIGINT PRIMARY KEY,
                    dimension JSON COMMENT '冗余维度，如 {"a": "x", "b": "y"}',
                    event_filter VARCHAR(64) COMMENT '事件过滤，如 event_type = ''play'''
                );
                """;
        var registry = new TableSchemaRegistry(sql);

        assertThat(registry.columnsOf("fact_tbl")).containsExactlyInAnyOrder("id", "dimension", "event_filter");
    }

    @Test
    void skipsIndexAndPrimaryKeyLines() {
        String sql = """
                CREATE TABLE IF NOT EXISTS agg_tbl (
                    date DATE NOT NULL,
                    category VARCHAR(32) NOT NULL,
                    total_plays BIGINT DEFAULT 0,
                    PRIMARY KEY (date, category)
                ) COMMENT='每日预聚合指标表';
                """;
        var registry = new TableSchemaRegistry(sql);

        assertThat(registry.columnsOf("agg_tbl")).containsExactlyInAnyOrder("date", "category", "total_plays");
    }

    @Test
    void loadsRealSchemaSql() {
        var registry = new TableSchemaRegistry();

        assertThat(registry.allTables()).containsKeys(
                "user_dim", "time_dim", "creator_dim", "content_dim", "activity_dim",
                "user_behavior_fact", "metric_definition", "metric_daily", "play_detail",
                "agent_run", "agent_run_node", "agent_audit_log");

        assertThat(registry.columnsOf("metric_daily"))
                .contains("date", "category", "total_plays", "total_likes");
        assertThat(registry.columnsOf("user_behavior_fact"))
                .contains("user_id", "event_type", "timestamp", "content_id");
        assertThat(registry.columnsOf("agent_run")).contains("run_id", "status");
        // 约束行不得混入列
        assertThat(registry.columnsOf("metric_daily")).doesNotContain("primary", "key", "index");
        assertThat(registry.columnsOf("user_behavior_fact")).doesNotContain("index", "idx_timestamp");
    }
}
