package com.yunzhu.video_data_analysis.dto;

public record RunNodeStartRequest(
        String nodeName,
        Object inputPayload
) {}
