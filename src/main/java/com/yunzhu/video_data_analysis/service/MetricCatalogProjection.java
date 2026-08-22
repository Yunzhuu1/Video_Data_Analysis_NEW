package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.dto.MetricDefinitionDto;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 指标目录参与血缘快照/运行时一致性校验的唯一 canonical projection。
 *
 * <p>数据库自增 id、owner、version、status 等治理字段不参与口径 hash；公式、物理来源和
 * fact 路径字段参与。所有消费者必须复用本类，禁止各自实现排序/字段选择。</p>
 */
public final class MetricCatalogProjection {

    private MetricCatalogProjection() {
    }

    public static List<Map<String, Object>> normalize(
            ObjectMapper mapper, List<MetricDefinitionDto> definitions) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (MetricDefinitionDto metric : definitions) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("metricCode", metric.metricCode());
            item.put("formula", metric.formula());
            item.put("dimensions", parseDimensions(mapper, metric.dimensions()));
            item.put("sourceTable", metric.sourceTable());
            item.put("timeField", metric.timeField());
            item.put("factFormula", metric.factFormula());
            item.put("factEventFilter", metric.factEventFilter());
            result.add(item);
        }
        result.sort(Comparator.comparing(item -> String.valueOf(item.get("metricCode"))));
        return List.copyOf(result);
    }

    public static String hash(ObjectMapper mapper, List<MetricDefinitionDto> definitions) {
        return CanonicalJson.sha256(mapper, mapper.valueToTree(normalize(mapper, definitions)));
    }

    static List<String> parseDimensions(ObjectMapper mapper, String raw) {
        if (raw == null || raw.isBlank()) {
            return List.of();
        }
        try {
            List<String> dimensions = mapper.readValue(raw, new TypeReference<>() {});
            return dimensions.stream().sorted().toList();
        } catch (Exception ignored) {
            return java.util.Arrays.stream(raw.split(","))
                    .map(String::trim)
                    .filter(value -> !value.isBlank())
                    .sorted()
                    .toList();
        }
    }
}
