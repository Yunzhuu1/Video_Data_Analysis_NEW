package com.yunzhu.video_data_analysis.dto;

/** One structured SQL validation issue returned by the hard guard. */
public record SqlViolation(
        String code,
        String severity,
        String message,
        String suggestion
) {}
