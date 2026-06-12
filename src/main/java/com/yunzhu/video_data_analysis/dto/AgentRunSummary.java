package com.yunzhu.video_data_analysis.dto;

import java.time.LocalDateTime;

public record AgentRunSummary(
        String runId,
        String userId,
        String question,
        String status,
        String currentNode,
        String errorMessage,
        LocalDateTime startedAt,
        LocalDateTime finishedAt,
        Long totalDurationMs
) {}
