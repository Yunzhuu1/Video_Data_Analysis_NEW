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
        Integer semanticPromptChars,
        String catalogVersion,
        String lineageHash,
        String metricCatalogHash,
        String schemaHash,
        List<Map<String, Object>> candidatePlans,
        List<Map<String, Object>> rejectedPlans,
        String selectedPlanId,
        String planSelectionSource,
        String plannerReasonCode,
        String plannerSkillVersion,
        Map<String, Object> planValidation,
        Integer planningRetryCount,
        List<String> lineageEdgeIds,
        Boolean legacyPlannerFallback,
        Integer plannerPromptChars,
        Double plannerLatencyMs
) {}
