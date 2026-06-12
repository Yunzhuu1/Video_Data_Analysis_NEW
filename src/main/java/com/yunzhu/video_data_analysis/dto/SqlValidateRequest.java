package com.yunzhu.video_data_analysis.dto;

/** Request for SQL hard validation before execution. */
public record SqlValidateRequest(
        String runId,
        String userId,
        String question,
        String sql,
        String purpose,
        boolean allowHighRisk
) {}
