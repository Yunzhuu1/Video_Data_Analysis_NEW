package com.yunzhu.video_data_analysis.dto;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;
import java.util.Map;

/** 单次 Agent run 使用的不可变血缘、指标与 schema 组合快照。 */
public record LineageSnapshotDto(
        String catalogVersion,
        String lineageHash,
        String metricCatalogHash,
        String schemaHash,
        JsonNode lineage,
        List<Map<String, Object>> metricDefinitions,
        Map<String, List<String>> schemaProjection) {}
