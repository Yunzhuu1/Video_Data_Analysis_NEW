package com.yunzhu.video_data_analysis.dto;

import java.util.List;

/** Structured SQL hard validation result returned before SQL execution. */
public record SqlValidateResult(
        boolean pass,
        String sql,
        String riskLevel,
        String errorCode,
        String reason,
        String suggestion,
        List<String> accessedTables,
        List<SqlViolation> violations
) {
    public static SqlValidateResult pass(String sql, String riskLevel, List<String> accessedTables,
                                         List<SqlViolation> warnings) {
        return new SqlValidateResult(true, sql, riskLevel, null, null, null, accessedTables, warnings);
    }

    public static SqlValidateResult rejected(String sql, String riskLevel, String errorCode,
                                             String reason, String suggestion,
                                             List<String> accessedTables,
                                             List<SqlViolation> violations) {
        return new SqlValidateResult(false, sql, riskLevel, errorCode, reason, suggestion,
                accessedTables, violations);
    }
}
