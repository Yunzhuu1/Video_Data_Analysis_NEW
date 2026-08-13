package com.yunzhu.video_data_analysis.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class AnalysisReportMappingTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void mapsPythonChatBIReportFields() {
        Map<String, Object> payload = Map.of(
                "status", "SUCCESS",
                "summary", "ok",
                "sql", "SELECT date, total_plays FROM metric_daily",
                "metrics", List.of(Map.of("name", "total_plays", "value", 100)),
                "charts", List.of(Map.of(
                        "type", "line",
                        "title", "plays by date",
                        "xField", "date",
                        "yField", "total_plays"
                )),
                "recommendations", List.of(),
                "warnings", List.of("partial data"),
                "dq", Map.of("riskLevel", "MEDIUM"),
                "extraFutureField", "ignored"
        );

        AnalysisReport report = objectMapper.convertValue(payload, AnalysisReport.class);

        assertThat(report.getStatus()).isEqualTo("SUCCESS");
        assertThat(report.getSummary()).isEqualTo("ok");
        assertThat(report.getSql()).startsWith("SELECT");
        assertThat(report.getWarnings()).containsExactly("partial data");
        assertThat(report.getDq()).containsEntry("riskLevel", "MEDIUM");
        assertThat(report.getCharts()).hasSize(1);
        assertThat(report.getCharts().get(0).getXField()).isEqualTo("date");
        assertThat(report.getCharts().get(0).getYField()).isEqualTo("total_plays");
    }

    @Test
    void mapsEngineAnalyzeResponseSqlSource() {
        Map<String, Object> payload = Map.of(
                "runId", "run-1",
                "status", "WAITING_APPROVAL",
                "finalReport", Map.of(),
                "warnings", List.of(),
                "approvalReason", "SQL_LARGE_SCAN",
                "resolvedIntent", Map.of("intent", "aggregate"),
                "sqlRetryCount", 0,
                "sqlSource", "semantic"
        );

        EngineAnalyzeResponse response = objectMapper.convertValue(payload, EngineAnalyzeResponse.class);

        assertThat(response.status()).isEqualTo("WAITING_APPROVAL");
        assertThat(response.sqlSource()).isEqualTo("semantic");
        assertThat(response.resolvedIntent()).containsEntry("intent", "aggregate");
    }
}
