package com.yunzhu.video_data_analysis.dto;

import java.util.List;

/** Result quality check used as a soft guard after SQL execution. */
public record SqlDQCheckResult(
        boolean pass,
        String riskLevel,
        String reason,
        String suggestion,
        List<String> warnings
) {}
