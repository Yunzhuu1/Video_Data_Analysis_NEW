package com.yunzhu.video_data_analysis.dto;

import java.time.LocalDateTime;

public record AgentRunNodeDetail(
        Long nodeId,
        String nodeName,
        String status,
        String inputPayload,
        String outputPayload,
        String errorMessage,
        String modelName,
        int promptTokens,
        int completionTokens,
        Long durationMs,
        int retryCount,
        LocalDateTime startedAt,
        LocalDateTime finishedAt
) {}
