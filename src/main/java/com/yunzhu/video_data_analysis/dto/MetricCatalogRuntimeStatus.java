package com.yunzhu.video_data_analysis.dto;

import java.util.List;

/** 不暴露公式/路径的指标目录运行时就绪投影。 */
public record MetricCatalogRuntimeStatus(
        String status,
        int managedCount,
        int activeCount,
        String managedCatalogHash,
        String runtimeCatalogHash,
        List<String> missingCodes,
        List<String> driftedCodes,
        List<String> extraCodes) {

    public static MetricCatalogRuntimeStatus notStarted() {
        return new MetricCatalogRuntimeStatus("NOT_STARTED", 0, 0, null, null,
                List.of(), List.of(), List.of());
    }
}
