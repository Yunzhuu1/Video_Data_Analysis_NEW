package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.dto.AnalysisReport;
import com.yunzhu.video_data_analysis.dto.EngineAnalyzeRequest;
import com.yunzhu.video_data_analysis.dto.EngineAnalyzeResponse;
import com.yunzhu.video_data_analysis.service.AgentRunQueryService;
import com.yunzhu.video_data_analysis.service.AgentRunTraceService;
import com.yunzhu.video_data_analysis.service.LangGraphClient;
import com.yunzhu.video_data_analysis.service.SchemaCatalogService;
import com.yunzhu.video_data_analysis.service.TokenUsageService;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import org.mockito.ArgumentCaptor;

/** 契约测试：includeDebug 默认关闭时业务响应不变，开启时 debug 携带观测数据。 */
class AgentControllerTest {

    private final TokenUsageService tokenUsageService = mock(TokenUsageService.class);
    private final AgentRunQueryService agentRunQueryService = mock(AgentRunQueryService.class);
    private final AgentRunTraceService agentRunTraceService = mock(AgentRunTraceService.class);
    private final LangGraphClient langGraphClient = mock(LangGraphClient.class);
    private final SchemaCatalogService schemaCatalogService = mock(SchemaCatalogService.class);
    private final AgentController controller = new AgentController(
            tokenUsageService, agentRunQueryService, agentRunTraceService, langGraphClient, schemaCatalogService);

    private EngineAnalyzeResponse successResponse() {
        return new EngineAnalyzeResponse(
                "run-1",
                "SUCCESS",
                Map.of("summary", "s", "sql", "SELECT 1", "metrics", List.of(),
                        "charts", List.of(), "recommendations", List.of()),
                List.of(),
                null,
                Map.of("intent", "aggregate", "metrics", List.of("total_plays")),
                2,
                "semantic",
                false,
                null,
                List.of(Map.of("metricCode", "total_plays", "score", 1.0)),
                "topk",
                false,
                null,
                5,
                1,
                5,
                15,
                5,
                1234,
                "catalog-v1", "lineage-h", "metric-h", "schema-h",
                List.of(Map.of("planId", "p1")), List.of(), "p1", "AUTO_SINGLE",
                null, null, Map.of("verdict", "PASS"), 0, List.of("play_content"),
                false, 0, 0.0
        );
    }

    @Test
    void analyzeWithoutIncludeDebugKeepsDebugNull() {
        when(agentRunTraceService.startRun("demo", "q")).thenReturn("run-1");
        when(langGraphClient.analyze(any(EngineAnalyzeRequest.class))).thenReturn(successResponse());

        AnalysisReport report = controller.analyze("demo", "q", false, false, "default");

        assertThat(report.getRunId()).isEqualTo("run-1");
        assertThat(report.getStatus()).isEqualTo("SUCCESS");
        assertThat(report.getDebug()).isNull();
    }

    @Test
    void analyzeWithIncludeDebugPopulatesDebug() {
        when(agentRunTraceService.startRun("demo", "q")).thenReturn("run-1");
        when(langGraphClient.analyze(any(EngineAnalyzeRequest.class))).thenReturn(successResponse());

        AnalysisReport report = controller.analyze("demo", "q", false, true, "default");

        assertThat(report.getDebug()).isNotNull();
        assertThat(report.getDebug()).containsEntry(
                "resolvedIntent", Map.of("intent", "aggregate", "metrics", List.of("total_plays")));
        assertThat(report.getDebug()).containsEntry("sqlRetryCount", 2);
        assertThat(report.getDebug()).containsEntry("sqlSource", "semantic");
        assertThat(report.getDebug()).containsEntry("memoryHit", false);
        assertThat(report.getDebug()).containsEntry("metricRecallMode", "topk");
        assertThat(report.getDebug()).containsEntry("metricRecallFallback", false);
        assertThat(report.getDebug()).containsEntry("metricRecallConfiguredK", 5);
        assertThat(report.getDebug()).containsEntry("metricRecallPinnedCount", 1);
        assertThat(report.getDebug()).containsEntry("metricRecallEffectiveK", 5);
        assertThat(report.getDebug()).containsEntry("metricRecallFullCatalogCount", 15);
        assertThat(report.getDebug()).containsEntry("metricRecallPromptCatalogCount", 5);
        assertThat(report.getDebug()).containsEntry("semanticPromptChars", 1234);
        assertThat(report.getDebug()).containsEntry("catalogVersion", "catalog-v1");
        assertThat(report.getDebug()).containsEntry("selectedPlanId", "p1");
        assertThat(report.getDebug()).containsEntry("planSelectionSource", "AUTO_SINGLE");
    }

    @Test
    void analyzeWaitingApprovalCarriesStatusAndDebug() {
        when(agentRunTraceService.startRun("demo", "q")).thenReturn("run-1");
        EngineAnalyzeResponse waiting = new EngineAnalyzeResponse(
                "run-1",
                "WAITING_APPROVAL",
                Map.of(),
                List.of(),
                "SQL_LARGE_SCAN",
                Map.of("intent", "aggregate", "metrics", List.of("total_plays")),
                0,
                "semantic",
                true,
                "hit",
                List.of(Map.of("metricCode", "total_plays", "score", 1.0)),
                "topk",
                false,
                null,
                5,
                1,
                5,
                15,
                5,
                null,
                null, null, null, null, null, null, null, null,
                null, null, null, null, null, null, null, null
        );
        when(langGraphClient.analyze(any(EngineAnalyzeRequest.class))).thenReturn(waiting);

        AnalysisReport report = controller.analyze("demo", "q", false, true, "default");

        assertThat(report.getStatus()).isEqualTo("WAITING_APPROVAL");
        assertThat(report.getSummary()).contains("waiting for human approval");
        assertThat(report.getDebug()).isNotNull();
        assertThat(report.getDebug()).containsEntry(
                "resolvedIntent", Map.of("intent", "aggregate", "metrics", List.of("total_plays")));
        assertThat(report.getDebug()).containsEntry("sqlSource", "semantic");
        assertThat(report.getDebug()).containsEntry("memoryHit", true);
    }

    @Test
    void analyzePassesThroughMemoryNamespace() {
        when(agentRunTraceService.startRun("demo", "q")).thenReturn("run-1");
        when(langGraphClient.analyze(any(EngineAnalyzeRequest.class))).thenReturn(successResponse());

        controller.analyze("demo", "q", false, false, "eval-2026-08-17-1234");

        ArgumentCaptor<EngineAnalyzeRequest> captor = ArgumentCaptor.forClass(EngineAnalyzeRequest.class);
        verify(langGraphClient).analyze(captor.capture());
        assertThat(captor.getValue().memoryNamespace()).isEqualTo("eval-2026-08-17-1234");
    }
}
