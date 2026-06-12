package com.yunzhu.video_data_analysis.dto;

import java.time.LocalDateTime;
import java.util.List;

public record AgentRunDetail(
        String runId,
        String userId,
        String question,
        String status,
        String currentNode,
        String finalReport,
        String errorMessage,
        LocalDateTime startedAt,
        LocalDateTime finishedAt,
        Long totalDurationMs,
        List<AgentRunNodeDetail> nodes
) {}
