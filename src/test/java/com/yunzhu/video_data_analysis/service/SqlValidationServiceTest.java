package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlValidateRequest;
import com.yunzhu.video_data_analysis.dto.SqlValidateResult;
import com.yunzhu.video_data_analysis.util.SqlParserValidator;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class SqlValidationServiceTest {

    private final SqlValidationService service = new SqlValidationService(new SqlParserValidator());

    @Test
    void acceptsSafeSelect() {
        SqlValidateResult result = service.validate(request(
                "SELECT date, category, total_plays FROM metric_daily LIMIT 10", false));

        assertThat(result.pass()).isTrue();
        assertThat(result.riskLevel()).isEqualTo("LOW");
        assertThat(result.accessedTables()).containsExactly("metric_daily");
        assertThat(result.violations()).isEmpty();
    }

    @Test
    void rejectsNonSelectStatement() {
        SqlValidateResult result = service.validate(request("DELETE FROM metric_daily", false));

        assertThat(result.pass()).isFalse();
        assertThat(result.riskLevel()).isEqualTo("HIGH");
        assertThat(result.errorCode()).isEqualTo("SQL_NOT_SELECT");
        assertThat(result.reason()).contains("Only SELECT");
    }

    @Test
    void rejectsDetailQueryWithoutLimit() {
        SqlValidateResult result = service.validate(request("SELECT * FROM play_detail", false));

        assertThat(result.pass()).isFalse();
        assertThat(result.riskLevel()).isEqualTo("HIGH");
        assertThat(result.errorCode()).isEqualTo("DETAIL_QUERY_WITHOUT_LIMIT");
        assertThat(result.violations())
                .extracting("code")
                .contains("DETAIL_QUERY_WITHOUT_LIMIT", "DETAIL_QUERY_WITHOUT_TIME_RANGE");
    }

    @Test
    void allowsApprovedHighRiskDetailQueryButKeepsViolations() {
        SqlValidateResult result = service.validate(request("SELECT * FROM play_detail", true));

        assertThat(result.pass()).isTrue();
        assertThat(result.riskLevel()).isEqualTo("HIGH");
        assertThat(result.violations()).isNotEmpty();
    }

    private static SqlValidateRequest request(String sql, boolean allowHighRisk) {
        return new SqlValidateRequest("run-test", "demo", "question", sql, "unit test", allowHighRisk);
    }
}
