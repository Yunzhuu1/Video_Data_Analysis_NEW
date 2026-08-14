package com.yunzhu.video_data_analysis.dto;

import java.util.List;

/**
 * 统一 SQL 门禁三态裁决结果。
 *
 * <p>verdict 取值：
 * <ul>
 *   <li>{@code PASS} — 可执行</li>
 *   <li>{@code RETRYABLE} — 有明确修复方向（语法/表/字段/逻辑规则），反馈给 LLM 重写</li>
 *   <li>{@code APPROVAL_NEEDED} — 高风险（明细无 LIMIT/时间范围、敏感列、FACT 全扫等），走 HITL 审批</li>
 * </ul>
 */
public record SqlGateResult(
        String verdict,
        String code,
        String reason,
        String suggestion,
        String riskLevel,
        List<String> accessedTables
) {
    public boolean pass() {
        return "PASS".equalsIgnoreCase(verdict);
    }

    public static SqlGateResult pass(String sql, List<String> accessedTables) {
        return new SqlGateResult("PASS", null, null, null, "LOW", accessedTables);
    }

    public static SqlGateResult retryable(String code, String reason, String suggestion,
                                          String riskLevel, List<String> accessedTables) {
        return new SqlGateResult("RETRYABLE", code, reason, suggestion, riskLevel, accessedTables);
    }

    public static SqlGateResult approvalNeeded(String code, String reason, String suggestion,
                                               List<String> accessedTables) {
        return new SqlGateResult("APPROVAL_NEEDED", code, reason, suggestion, "HIGH", accessedTables);
    }
}
