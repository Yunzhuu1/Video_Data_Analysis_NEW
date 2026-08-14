package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlExecuteRequest;
import com.yunzhu.video_data_analysis.dto.SqlExecuteResult;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.ColumnMapRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.PreparedStatementCreator;
import org.springframework.jdbc.core.RowMapper;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 执行网关契约（D8 审批放行不变式）：execute 只执行 + 熔断，不再承担门禁检查。
 */
class SqlExecutionServiceTest {

    private final JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
    private final SqlAuditService sqlAuditService = mock(SqlAuditService.class);
    private final SqlExecutionService service = new SqlExecutionService(jdbcTemplate, sqlAuditService);

    @Test
    void executesQueryAndReturnsRows() {
        when(jdbcTemplate.query(any(PreparedStatementCreator.class), any(RowMapper.class)))
                .thenReturn(List.of(Map.of("category", "美食", "total_plays", 3828)));

        SqlExecuteResult result = service.execute(request(
                "SELECT md.category AS category, SUM(total_plays) AS total_plays "
                        + "FROM metric_daily md GROUP BY md.category", false));

        assertThat(result.success()).isTrue();
        assertThat(result.rowCount()).isEqualTo(1);
        verify(sqlAuditService).record(any(SqlExecuteRequest.class), any(SqlExecuteResult.class));
    }

    @Test
    void returnsExecutionErrorOnFailure() {
        when(jdbcTemplate.query(any(PreparedStatementCreator.class), any(RowMapper.class)))
                .thenThrow(new RuntimeException("SQL syntax error near 'FROM'"));

        SqlExecuteResult result = service.execute(request("SELECT bogus", false));

        assertThat(result.success()).isFalse();
        assertThat(result.errorCode()).isEqualTo("SQL_EXECUTION_ERROR");
        verify(sqlAuditService).record(any(SqlExecuteRequest.class), any(SqlExecuteResult.class));
    }

    @Test
    void circuitBreakerBlocksAfterRepeatedTimeouts() {
        when(jdbcTemplate.query(any(PreparedStatementCreator.class), any(RowMapper.class)))
                .thenThrow(new RuntimeException("Query timeout expired"));

        SqlExecuteRequest req = request("SELECT 1", false);
        for (int i = 0; i < 3; i++) {
            SqlExecuteResult r = service.execute(req);
            assertThat(r.errorCode()).isEqualTo("SQL_EXECUTION_ERROR");
        }

        // 第 4 次触发熔断，不再触碰 DB
        SqlExecuteResult blocked = service.execute(req);
        assertThat(blocked.errorCode()).isEqualTo("SQL_CIRCUIT_BREAKER");
        assertThat(blocked.riskLevel()).isEqualTo("HIGH");
    }

    private static SqlExecuteRequest request(String sql, boolean allowHighRisk) {
        return new SqlExecuteRequest("run-test", "demo", "question", sql, "unit test", allowHighRisk);
    }
}
