package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.dto.RunNodeStartRequest;
import com.yunzhu.video_data_analysis.dto.RunNodeUpdateRequest;
import com.yunzhu.video_data_analysis.service.AgentRunTraceService;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** Internal Run Trace endpoint for LangGraph Agent Engine node lifecycle callbacks. */
@RestController
@RequestMapping("/internal/runs")
public class InternalRunController {

    private final AgentRunTraceService traceService;

    public InternalRunController(AgentRunTraceService traceService) {
        this.traceService = traceService;
    }

    @PostMapping("/{runId}/nodes")
    public Map<String, Object> startNode(@PathVariable String runId,
                                         @RequestBody RunNodeStartRequest request) {
        Long nodeId = traceService.startNode(runId, request.nodeName(), request.inputPayload());
        return Map.of("success", true, "nodeId", nodeId);
    }

    @PatchMapping("/{runId}/nodes/{nodeId}")
    public Map<String, Object> updateNode(@PathVariable String runId,
                                          @PathVariable Long nodeId,
                                          @RequestBody RunNodeUpdateRequest request) {
        if ("FAILED".equalsIgnoreCase(request.status())) {
            traceService.failNode(nodeId, request.errorMessage());
        } else {
            traceService.finishNode(nodeId, request.outputPayload());
        }
        return Map.of("success", true);
    }
}
