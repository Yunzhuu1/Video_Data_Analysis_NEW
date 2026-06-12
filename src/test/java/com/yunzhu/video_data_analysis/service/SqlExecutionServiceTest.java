package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlExecuteRequest;
import com.yunzhu.video_data_analysis.dto.SqlExecuteResult;
import com.yunzhu.video_data_analysis.tool.SqlRulesChecker;
import com.yunzhu.video_data_analysis.util.SqlParserValidator;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

class SqlExecutionServiceTest {

    private final JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
    private final SqlResultCache sqlResultCache = mock(SqlResultCache.class);
    private final SqlRulesChecker sqlRulesChecker = mock(SqlRulesChecker.class);
    private final SqlParserValidator sqlParserValidator = new SqlParserValidator();
    private final SqlValidationService sqlValidationService = new SqlValidationService(sqlParserValidator);
    private final SlowQueryService slowQueryService = mock(SlowQueryService.class);
    private final SqlAuditService sqlAuditService = mock(SqlAuditService.class);
    private final SqlExecutionService service = new SqlExecutionService(
            jdbcTemplate,
            sqlResultCache,
            sqlRulesChecker,
            sqlParserValidator,
            sqlValidationService,
            slowQueryService,
            sqlAuditService
    );

    @Test
    void executeRejectsNonSelectThroughHardGuard() {
        SqlExecuteRequest request = request("DELETE FROM metric_daily", false);

        SqlExecuteResult result = service.execute(request);

        assertThat(result.success()).isFalse();
        assertThat(result.errorCode()).isEqualTo("SQL_NOT_SELECT");
        assertThat(result.riskLevel()).isEqualTo("HIGH");
        verify(sqlAuditService).record(request, result);
        verifyNoInteractions(jdbcTemplate, sqlResultCache, sqlRulesChecker, slowQueryService);
    }

    @Test
    void executeRejectsHighRiskDetailQueryBeforeDatabaseAccess() {
        SqlExecuteRequest request = request("SELECT * FROM play_detail", false);

        SqlExecuteResult result = service.execute(request);

        assertThat(result.success()).isFalse();
        assertThat(result.errorCode()).isEqualTo("DETAIL_QUERY_WITHOUT_LIMIT");
        assertThat(result.riskLevel()).isEqualTo("HIGH");
        assertThat(result.accessedTables()).containsExactly("play_detail");
        verify(sqlAuditService).record(request, result);
        verifyNoInteractions(jdbcTemplate, sqlResultCache, sqlRulesChecker, slowQueryService);
    }

    private static SqlExecuteRequest request(String sql, boolean allowHighRisk) {
        return new SqlExecuteRequest("run-test", "demo", "question", sql, "unit test", allowHighRisk);
    }
}
