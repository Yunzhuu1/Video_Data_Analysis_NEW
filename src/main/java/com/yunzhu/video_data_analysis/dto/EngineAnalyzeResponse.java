package com.yunzhu.video_data_analysis.dto;

import java.util.List;
import java.util.Map;

public record EngineAnalyzeResponse(
        String runId,
        String status,
        Map<String, Object> finalReport,
        List<String> warnings,
        String approvalReason
) {}
