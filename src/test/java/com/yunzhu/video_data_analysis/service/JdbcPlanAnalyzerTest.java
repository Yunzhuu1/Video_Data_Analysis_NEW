package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.dto.SqlGateResult;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/** 计划层表类型感知测试：EXPLAIN JSON 由 mock JdbcTemplate 提供，不依赖真实 DB。 */
class JdbcPlanAnalyzerTest {

    private final JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
    private final SlowQueryService slowQueryService = mock(SlowQueryService.class);
    private final JdbcPlanAnalyzer analyzer =
            new JdbcPlanAnalyzer(jdbcTemplate, new ObjectMapper(), slowQueryService);

    private void stubPlan(String json) {
        when(jdbcTemplate.queryForObject(anyString(), eq(String.class))).thenReturn(json);
    }

    private static String tableJson(String tableName, String accessType, long rows) {
        return "{\"query_block\":{\"select_id\":1,\"table\":{"
                + "\"table_name\":\"" + tableName + "\","
                + "\"access_type\":\"" + accessType + "\","
                + "\"rows_examined_per_scan\":" + rows + "}}}";
    }

    @Test
    void factFullScanApproves() {
        stubPlan(tableJson("user_behavior_fact", "ALL", 1000000));

        SqlGateResult r = analyzer.analyzePlan("SELECT * FROM user_behavior_fact",
                List.of("user_behavior_fact"));

        assertThat(r.verdict()).isEqualTo("APPROVAL_NEEDED");
        assertThat(r.code()).isEqualTo("SQL_FULL_SCAN");
    }

    @Test
    void aggregateFullScanPasses() {
        stubPlan(tableJson("metric_daily", "ALL", 93));

        SqlGateResult r = analyzer.analyzePlan("SELECT * FROM metric_daily", List.of("metric_daily"));

        assertThat(r).isNull();
    }

    @Test
    void tempTableOnFactRetryable() {
        stubPlan("{\"query_block\":{\"select_id\":1,"
                + "\"table\":{\"table_name\":\"user_behavior_fact\",\"access_type\":\"ref\"},"
                + "\"ordering_operation\":{\"using_temporary_table\":true}}}");

        SqlGateResult r = analyzer.analyzePlan("SELECT * FROM user_behavior_fact ORDER BY x",
                List.of("user_behavior_fact"));

        assertThat(r.verdict()).isEqualTo("RETRYABLE");
        assertThat(r.code()).isEqualTo("SQL_TEMP_TABLE");
    }

    @Test
    void tempTableOnAggregatePasses() {
        stubPlan("{\"query_block\":{\"select_id\":1,"
                + "\"table\":{\"table_name\":\"metric_daily\",\"access_type\":\"ALL\"},"
                + "\"grouping_operation\":{\"using_temporary_table\":true}}}");

        SqlGateResult r = analyzer.analyzePlan(
                "SELECT category, SUM(total_plays) FROM metric_daily GROUP BY category",
                List.of("metric_daily"));

        assertThat(r).isNull();
    }

    @Test
    void largeScanOnFactApproves() {
        stubPlan(tableJson("user_behavior_fact", "index", 500000));

        SqlGateResult r = analyzer.analyzePlan("SELECT * FROM user_behavior_fact WHERE timestamp > '2023-01-01'",
                List.of("user_behavior_fact"));

        assertThat(r.verdict()).isEqualTo("APPROVAL_NEEDED");
        assertThat(r.code()).isEqualTo("SQL_LARGE_SCAN");
    }
}
