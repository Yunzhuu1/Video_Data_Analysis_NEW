package com.yunzhu.video_data_analysis.dto;

public record RunNodeUpdateRequest(
        String status,
        Object outputPayload,
        String errorMessage,
        String modelName,
        int promptTokens,
        int completionTokens
) {}
