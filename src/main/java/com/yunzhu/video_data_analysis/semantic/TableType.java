package com.yunzhu.video_data_analysis.semantic;

import java.util.Locale;
import java.util.Set;

/**
 * 表类型分类（schema 契约，设计期确定，非运行时启发式）。
 *
 * <p>全表扫描的风险取决于表类型：FACT/明细表行数无界（危险），AGGREGATE 预聚合表
 * 行数有界（schema 设计保证），DIM 维度表可忽略。未知表返回 {@code null}，
 * 由门禁统一按 RETRYABLE 处理（LLM 臆测，重写优先；从严体现在绝不放行）。
 */
public enum TableType {
    FACT, AGGREGATE, DIM;

    private static final Set<String> FACT_TABLES = Set.of(
            "user_behavior_fact", "play_detail",
            "creator_revenue", "video_revenue", "user_retention");  // scale-data 新 FACT 表
    private static final Set<String> AGGREGATE_TABLES = Set.of("metric_daily");

    /** 按表名分类；未知表返回 null（门禁层决定裁决）。 */
    public static TableType classify(String table) {
        if (table == null) {
            return null;
        }
        String name = table.toLowerCase(Locale.ROOT);
        if (FACT_TABLES.contains(name)) {
            return FACT;
        }
        if (AGGREGATE_TABLES.contains(name)) {
            return AGGREGATE;
        }
        if (name.endsWith("_dim")) {
            return DIM;
        }
        return null;
    }
}
