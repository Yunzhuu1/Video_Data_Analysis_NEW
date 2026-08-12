package com.yunzhu.video_data_analysis.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.dto.AgentRunDetail;
import com.yunzhu.video_data_analysis.dto.AgentRunSummary;
import com.yunzhu.video_data_analysis.dto.AnalysisReport;
import com.yunzhu.video_data_analysis.dto.EngineAnalyzeRequest;
import com.yunzhu.video_data_analysis.dto.EngineAnalyzeResponse;
import com.yunzhu.video_data_analysis.dto.EngineApprovalRequest;
import com.yunzhu.video_data_analysis.service.AgentRunQueryService;
import com.yunzhu.video_data_analysis.service.AgentRunTraceService;
import com.yunzhu.video_data_analysis.service.LangGraphClient;
import com.yunzhu.video_data_analysis.service.SchemaCatalogService;
import com.yunzhu.video_data_analysis.service.TokenUsageService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * ChatBI 对外入口。当前主链路：Spring Boot 只做平台治理与转发，
 * 编排统一由 Python LangGraph Agent Engine 完成。
 */
@RestController
@RequestMapping("/api/agent")
public class AgentController {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final TokenUsageService tokenUsageService;
    private final AgentRunQueryService agentRunQueryService;
    private final AgentRunTraceService agentRunTraceService;
    private final LangGraphClient langGraphClient;
    private final SchemaCatalogService schemaCatalogService;

    public AgentController(TokenUsageService tokenUsageService,
                           AgentRunQueryService agentRunQueryService,
                           AgentRunTraceService agentRunTraceService,
                           LangGraphClient langGraphClient,
                           SchemaCatalogService schemaCatalogService) {
        this.tokenUsageService = tokenUsageService;
        this.agentRunQueryService = agentRunQueryService;
        this.agentRunTraceService = agentRunTraceService;
        this.langGraphClient = langGraphClient;
        this.schemaCatalogService = schemaCatalogService;
    }

    /** 结构化分析（同步 JSON，LangGraph 主线），nocache=true 时转发给引擎跳过缓存 */
    @GetMapping("/analyze")
    public AnalysisReport analyze(@RequestParam String userId, @RequestParam String message,
                                  @RequestParam(defaultValue = "false") boolean nocache) {
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

    @PostMapping("/admin/tokens/clear")
    public Map<String, String> clearTokens() {
        tokenUsageService.clear();
        return Map.of("status", "ok");
    }

    /** 手动刷新 Schema 缓存（DDL 变更后调用） */
    @PostMapping("/admin/schema/refresh")
    public Map<String, String> refreshSchema() {
        schemaCatalogService.refresh();
        return Map.of("status", "ok", "message", "Schema cache refreshed");
    }
}
