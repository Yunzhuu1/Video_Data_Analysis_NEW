package com.yunzhu.video_data_analysis.dto;

/** 指标字典条目（metric_definition 行映射）。 */
public record MetricDefinitionDto(
        Long id,
        String metricName,
        String metricCode,
        String businessDefinition,
        String formula,
        String dimensions,
        String timeGranularity,
        String sourceTable,
        String timeField,
        String factFormula,
        String factEventFilter,
        String owner,
        Integer version,
        String status) {}
