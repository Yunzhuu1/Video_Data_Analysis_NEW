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
                null
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
                "hit"
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
