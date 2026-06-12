package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlDQCheckRequest;
import com.yunzhu.video_data_analysis.dto.SqlDQCheckResult;
import com.yunzhu.video_data_analysis.dto.SqlExecuteResult;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class SqlResultDQServiceTest {

    private final SqlResultDQService service = new SqlResultDQService();

    @Test
    void rejectsTrendResultWithoutTimeColumn() {
        SqlDQCheckResult result = service.check(request(
                "analyze play trend",
                success(List.of("category", "total_plays"), List.of(Map.of("category", "food", "total_plays", 10))),
                false
        ));

        assertThat(result.pass()).isFalse();
        assertThat(result.reason()).contains("time column");
    }

    @Test
    void rejectsEmptyResult() {
        SqlDQCheckResult result = service.check(request(
                "compare category plays",
                success(List.of(), List.of()),
                false
        ));

        assertThat(result.pass()).isFalse();
        assertThat(result.riskLevel()).isEqualTo("HIGH");
        assertThat(result.reason()).contains("empty");
    }

    @Test
    void warnsOnTruncatedResult() {
        SqlDQCheckResult result = service.check(request(
                "compare category plays",
                success(List.of("category", "total_plays"), List.of(Map.of("category", "food", "total_plays", 10))),
                true
        ));

        assertThat(result.pass()).isTrue();
        assertThat(result.riskLevel()).isEqualTo("MEDIUM");
        assertThat(result.warnings()).contains("Result was truncated; answer should mention partial data.");
    }

    @Test
    void rejectsInvalidCompletionRate() {
        SqlDQCheckResult result = service.check(request(
                "analyze completion rate",
                success(List.of("date", "completion_rate"), List.of(Map.of("date", "2026-01-01", "completion_rate", 120))),
                false
        ));

        assertThat(result.pass()).isFalse();
        assertThat(result.reason()).contains("Completion rate");
    }

    private static SqlDQCheckRequest request(String question, SqlExecuteResult queryResult, boolean truncated) {
        SqlExecuteResult adjusted = new SqlExecuteResult(
                queryResult.success(),
                queryResult.sql(),
                queryResult.resultText(),
                queryResult.columns(),
                queryResult.rows(),
                queryResult.rowCount(),
                truncated,
                queryResult.warnings(),
                queryResult.errorCode(),
                queryResult.error(),
                queryResult.riskLevel(),
                queryResult.accessedTables(),
                queryResult.durationMs()
        );
        return new SqlDQCheckRequest("run-test", "demo", question, adjusted);
    }

    private static SqlExecuteResult success(List<String> columns, List<Map<String, Object>> rows) {
        return new SqlExecuteResult(true, "SELECT 1", null, columns, rows, rows.size(), false,
                List.of(), null, null, "LOW", List.of("metric_daily"), 1);
    }
}
