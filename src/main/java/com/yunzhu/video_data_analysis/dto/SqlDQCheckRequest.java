package com.yunzhu.video_data_analysis.dto;

/** Request for checking whether SQL result can answer the ChatBI question. */
public record SqlDQCheckRequest(
        String runId,
        String userId,
        String question,
        SqlExecuteResult queryResult
) {}
