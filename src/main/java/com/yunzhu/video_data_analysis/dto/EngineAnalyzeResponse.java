package com.yunzhu.video_data_analysis.dto;

import java.util.List;
import java.util.Map;

public record EngineAnalyzeResponse(
        String runId,
        String status,
        Map<String, Object> finalReport,
        List<String> warnings,
        String approvalReason,
        Map<String, Object> resolvedIntent,
        Integer sqlRetryCount,
        String sqlSource,
        Boolean memoryHit,
        String memoryBand,
        List<Map<String, Object>> metricCandidates,
        String metricRecallMode,
        Boolean metricRecallFallback,
        String metricRecallReason,
        Integer metricRecallConfiguredK,
        Integer metricRecallPinnedCount,
        Integer metricRecallEffectiveK,
        Integer metricRecallFullCatalogCount,
        Integer metricRecallPromptCatalogCount,
        Integer semanticPromptChars
) {}
