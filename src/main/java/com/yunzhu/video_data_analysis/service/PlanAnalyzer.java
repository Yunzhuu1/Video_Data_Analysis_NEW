package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlGateResult;

import java.util.List;

/**
 * 门禁计划层：基于 EXPLAIN 判定候选 SQL 的执行风险。
 * 独立为接口以便单测可桩（不依赖真实 DB）。
 *
 * <p>返回 {@code null} 表示计划层通过；否则返回对应裁决（FACT 全扫→APPROVAL_NEEDED、
 * TEMP_TABLE/FILESORT→RETRYABLE、大行数且 FACT→APPROVAL_NEEDED）。
 */
public interface PlanAnalyzer {

    SqlGateResult analyzePlan(String sql, List<String> accessedTables);
}
