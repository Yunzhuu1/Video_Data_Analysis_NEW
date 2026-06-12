package com.yunzhu.video_data_analysis.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.agent.DataAnalysisAgent;
import com.yunzhu.video_data_analysis.agent.SchemaAgent;
import com.yunzhu.video_data_analysis.dto.AgentRunDetail;
import com.yunzhu.video_data_analysis.dto.AgentRunSummary;
import com.yunzhu.video_data_analysis.dto.AnalysisReport;
import com.yunzhu.video_data_analysis.dto.EngineAnalyzeRequest;
import com.yunzhu.video_data_analysis.dto.EngineAnalyzeResponse;
import com.yunzhu.video_data_analysis.dto.EngineApprovalRequest;
import com.yunzhu.video_data_analysis.service.AgentRunQueryService;
import com.yunzhu.video_data_analysis.service.AgentRunTraceService;
import com.yunzhu.video_data_analysis.service.LangGraphClient;
import com.yunzhu.video_data_analysis.service.SemanticCacheService;
import com.yunzhu.video_data_analysis.service.TokenUsageService;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;

import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

@RestController
@RequestMapping("/api/agent")
public class AgentController {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final DataAnalysisAgent dataAnalysisAgent;
    private final SchemaAgent schemaAgent;
    private final SemanticCacheService cacheService;
    private final TokenUsageService tokenUsageService;
    private final AgentRunQueryService agentRunQueryService;
    private final AgentRunTraceService agentRunTraceService;
    private final LangGraphClient langGraphClient;
    private final Executor agentExecutor;

    public AgentController(DataAnalysisAgent dataAnalysisAgent,
                           SchemaAgent schemaAgent,
                           SemanticCacheService cacheService,
                           TokenUsageService tokenUsageService,
                           AgentRunQueryService agentRunQueryService,
                           AgentRunTraceService agentRunTraceService,
                           LangGraphClient langGraphClient,
                           @Qualifier("agentTaskExecutor") Executor agentExecutor) {
        this.dataAnalysisAgent = dataAnalysisAgent;
        this.schemaAgent = schemaAgent;
        this.cacheService = cacheService;
        this.tokenUsageService = tokenUsageService;
        this.agentRunQueryService = agentRunQueryService;
        this.agentRunTraceService = agentRunTraceService;
        this.langGraphClient = langGraphClient;
        this.agentExecutor = agentExecutor;
    }

    /** SSE 流式对话 */
    @GetMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> chat(@RequestParam String userId, @RequestParam String message) {
        return dataAnalysisAgent.chat(userId, message);
    }

    /** 结构化分析（同步 JSON），传 nocache=true 跳过语义缓存 */
    @GetMapping("/analyze")
    public AnalysisReport analyze(@RequestParam String userId, @RequestParam String message,
                                  @RequestParam(defaultValue = "false") boolean nocache,
                                  @RequestParam(defaultValue = "spring") String engine) {
        if ("langgraph".equalsIgnoreCase(engine)) {
            return analyzeWithLangGraph(userId, message, nocache);
        }
        return dataAnalysisAgent.analyze(userId, message, null, nocache);
    }

    /** 结构化分析（SSE 流式，每步推送进度事件），传 nocache=true 跳过语义缓存 */
    @GetMapping(value = "/analyze-stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> analyzeStream(@RequestParam String userId, @RequestParam String message,
                                      @RequestParam(defaultValue = "false") boolean nocache) {
        Sinks.Many<String> sink = Sinks.many().unicast().onBackpressureBuffer();

        boolean skipCache = nocache;
        CompletableFuture.runAsync(() -> {
            try {
                dataAnalysisAgent.analyze(userId, message, progress -> {
                    sink.tryEmitNext("data: {\\\"type\\\":\\\"progress\\\",\\\"message\\\":\\\""
                            + progress + "\\\"}\n\n");
                }, skipCache);
                sink.tryEmitNext("data: {\"type\":\"complete\"}\n\n");
            } catch (Exception e) {
                sink.tryEmitNext("data: {\"type\":\"error\",\"message\":\"" + e.getMessage() + "\"}\n\n");
            } finally {
                sink.tryEmitComplete();
            }
        }, agentExecutor);

        return sink.asFlux();
    }

    private AnalysisReport analyzeWithLangGraph(String userId, String message, boolean nocache) {
        String runId = agentRunTraceService.startRun(userId, message);
        try {
            EngineAnalyzeResponse response = langGraphClient.analyze(
                    new EngineAnalyzeRequest(runId, userId, message, nocache));
            if ("WAITING_APPROVAL".equalsIgnoreCase(response.status())) {
                AnalysisReport waiting = waitingApprovalReport(runId, response.approvalReason());
                agentRunTraceService.waitForApprovalRun(runId, response.approvalReason());
                return waiting;
            }
            AnalysisReport report = MAPPER.convertValue(response.finalReport(), AnalysisReport.class);
            report.setRunId(runId);
            agentRunTraceService.finishRun(runId, report);
            return report;
        } catch (Exception e) {
            agentRunTraceService.failRun(runId, e);
            throw e;
        }
    }

    @PostMapping("/runs/{runId}/approval")
    public AnalysisReport approveLangGraphRun(@PathVariable String runId,
                                              @RequestParam(required = false) Boolean approved,
                                              @RequestBody(required = false) EngineApprovalRequest body) {
        boolean decision = body != null ? body.approved() : approved == null || approved;
        EngineAnalyzeResponse response = langGraphClient.approve(runId, decision);
        if ("REJECTED".equalsIgnoreCase(response.status())) {
            AnalysisReport rejected = MAPPER.convertValue(response.finalReport(), AnalysisReport.class);
            rejected.setRunId(runId);
            agentRunTraceService.failRun(runId, new IllegalStateException("High-risk SQL rejected"));
            return rejected;
        }
        AnalysisReport report = MAPPER.convertValue(response.finalReport(), AnalysisReport.class);
        report.setRunId(runId);
        agentRunTraceService.finishRun(runId, report);
        return report;
    }

    private static AnalysisReport waitingApprovalReport(String runId, String reason) {
        AnalysisReport report = new AnalysisReport();
        report.setRunId(runId);
        report.setSummary("Analysis is waiting for human approval before running high-risk SQL. Reason: "
                + (reason == null || reason.isBlank() ? "SQL Gateway marked the query as high risk" : reason));
        report.setPeriod("-");
        report.setRecommendations(java.util.List.of("Review the SQL risk reason and approve or reject this run."));
        return report;
    }

    // ==================== Admin ====================

    @GetMapping("/admin/cache")
    public Map<String, Object> cacheStats() {
        return Map.of("size", cacheService.size(), "threshold", 0.92);
    }

    @GetMapping("/admin/tokens")
    public TokenUsageService.TokenStats tokenStats() {
        return tokenUsageService.summary();
    }

    @GetMapping("/admin/recent")
    public java.util.List<TokenUsageService.UsageRecord> recentUsage() {
        return tokenUsageService.recent(20);
    }

    @GetMapping("/admin/runs")
    public java.util.List<AgentRunSummary> recentRuns(@RequestParam(defaultValue = "20") int limit) {
        return agentRunQueryService.listRecentRuns(limit);
    }

    @GetMapping("/admin/runs/{runId}")
    public AgentRunDetail runDetail(@PathVariable String runId) {
        return agentRunQueryService.getRunDetail(runId);
    }

    @GetMapping("jiegouhua/stats")
    public Map<String, Object> stats() {
        var tokenStats = tokenUsageService.summary();
        return Map.of(
                "cache", Map.of("size", cacheService.size(), "threshold", 0.92),
                "tokens", Map.of(
                        "totalCalls", tokenStats.totalCalls(),
                        "totalPromptTokens", tokenStats.totalPromptTokens(),
                        "totalCompletionTokens", tokenStats.totalCompletionTokens(),
                        "totalTokens", tokenStats.totalTokens(),
                        "totalCostUsd", tokenStats.totalCostUsd(),
                        "cachedCount", tokenStats.cachedCount(),
                        "uncachedCount", tokenStats.uncachedCount()
                )
        );
    }

    @PostMapping("/admin/cache/clear")
    public Map<String, String> clearCache() {
        cacheService.clear();
        return Map.of("status", "ok");
    }

    @PostMapping("/admin/tokens/clear")
    public Map<String, String> clearTokens() {
        tokenUsageService.clear();
        return Map.of("status", "ok");
    }

    /** 手动刷新 Schema 缓存（DDL 变更后调用） */
    @PostMapping("/admin/schema/refresh")
    public Map<String, String> refreshSchema() {
        schemaAgent.refresh();
        return Map.of("status", "ok", "message", "Schema cache refreshed");
    }
}
