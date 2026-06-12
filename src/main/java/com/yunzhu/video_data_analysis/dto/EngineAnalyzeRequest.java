package com.yunzhu.video_data_analysis.dto;

public record EngineAnalyzeRequest(
        String runId,
        String userId,
        String question,
        boolean bypassCache
) {}
