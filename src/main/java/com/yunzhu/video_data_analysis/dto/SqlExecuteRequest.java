package com.yunzhu.video_data_analysis.dto;

/** Structured request for the platform SQL execution gateway. */
public record SqlExecuteRequest(
        String runId,
        String userId,
        String question,
        String sql,
        String purpose,
        boolean allowHighRisk
) {
    public static SqlExecuteRequest toolRequest(String sql) {
        return new SqlExecuteRequest(null, "agent-tool", null, sql, "LLM tool execution", false);
    }
}
