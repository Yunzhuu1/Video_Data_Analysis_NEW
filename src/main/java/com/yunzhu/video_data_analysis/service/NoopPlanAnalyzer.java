package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlGateResult;
import org.springframework.stereotype.Component;

import java.util.List;

/** 计划层占位实现：总是通过。Stage 3 由 {@link JdbcPlanAnalyzer} 替换。 */
@Component
public class NoopPlanAnalyzer implements PlanAnalyzer {

    @Override
    public SqlGateResult analyzePlan(String sql, List<String> accessedTables) {
        return null;
    }
}
