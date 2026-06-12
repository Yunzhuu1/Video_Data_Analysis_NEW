package com.yunzhu.video_data_analysis.dto;

import java.util.List;
import java.util.Map;

/** Structured result returned by the platform SQL execution gateway. */
public record SqlExecuteResult(
        boolean success,
        String sql,
        String resultText,
        List<String> columns,
        List<Map<String, Object>> rows,
        int rowCount,
        boolean truncated,
        List<String> warnings,
        String errorCode,
        String error,
        String riskLevel,
        List<String> accessedTables,
        long durationMs
) {
    public static SqlExecuteResult rejected(String sql, String errorCode, String error) {
        return new SqlExecuteResult(false, sql, error, List.of(), List.of(), 0, false,
                List.of(), errorCode, error, "LOW", List.of(), 0);
    }

    public String toToolResponse() {
        if (resultText != null && !resultText.isEmpty()) {
            return resultText;
        }
        if (!success) {
            return error;
        }

        StringBuilder sb = new StringBuilder();
        sb.append(rowCount).append(" rows\n");
        if (!columns.isEmpty()) {
            sb.append(String.join("|", columns)).append("\n");
        }
        for (Map<String, Object> row : rows) {
            sb.append(String.join("|", row.values().stream()
                    .map(v -> v == null ? "" : v.toString())
                    .toArray(String[]::new))).append("\n");
        }
        if (truncated) {
            sb.append("... [").append(rowCount).append("+ rows, truncated]");
        }
        return sb.toString();
    }
}
