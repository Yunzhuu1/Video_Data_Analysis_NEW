package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.dto.MetricDefinitionDto;
import com.yunzhu.video_data_analysis.semantic.TableSchemaRegistry;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** 加载并校验 Git/classpath 版本化的受管指标目录。 */
@Component
public class MetricCatalogResource {

    static final String RESOURCE = "metric_catalog.json";
    static final String LINEAGE_RESOURCE = "lineage_catalog.json";

    private final ObjectMapper mapper;
    private final TableSchemaRegistry schemas;

    public MetricCatalogResource(ObjectMapper mapper, TableSchemaRegistry schemas) {
        this.mapper = mapper;
        this.schemas = schemas;
    }

    public List<ManagedMetric> load() {
        return parse(read(RESOURCE), read(LINEAGE_RESOURCE));
    }

    List<ManagedMetric> parse(JsonNode catalog, JsonNode lineage) {
        if (!catalog.isArray() || catalog.isEmpty()) {
            throw invalid("catalog must be a non-empty array");
        }
        Set<String> codes = new HashSet<>();
        List<ManagedMetric> metrics = new ArrayList<>();
        for (JsonNode item : catalog) {
            String code = requiredText(item, "metricCode");
            if (!codes.add(code)) {
                throw invalid("duplicate metricCode: " + code);
            }
            String name = requiredText(item, "metricName");
            String definition = requiredText(item, "businessDefinition");
            String formula = nullableText(item, "formula");
            String factFormula = nullableText(item, "factFormula");
            if (blank(formula) && blank(factFormula)) {
                throw invalid("metric has no usable expression: " + code);
            }
            JsonNode dimensionsNode = item.get("dimensions");
            if (dimensionsNode == null || !dimensionsNode.isArray()) {
                throw invalid("dimensions must be an array: " + code);
            }
            List<String> dimensions = new ArrayList<>();
            for (JsonNode dimension : dimensionsNode) {
                if (!dimension.isTextual() || dimension.asText().isBlank()) {
                    throw invalid("dimensions must contain non-empty strings: " + code);
                }
                dimensions.add(dimension.asText());
            }
            String source = requiredText(item, "sourceTable");
            String timeField = requiredText(item, "timeField");
            if (!schemas.hasTable(source)) {
                throw invalid("unknown sourceTable for " + code + ": " + source);
            }
            if (!schemas.hasColumn(source, timeField)) {
                throw invalid("unknown timeField for " + code + ": " + source + "." + timeField);
            }
            metrics.add(new ManagedMetric(
                    name, code, definition, formula,
                    writeJson(dimensions), nullableText(item, "timeGranularity"),
                    source, timeField, factFormula, nullableText(item, "factEventFilter")));
        }
        if (lineage == null || !lineage.isObject()) {
            throw invalid("lineage catalog must be an object");
        }
        lineage.path("metricPaths").forEach(path -> {
            String code = path.path("metricCode").asText();
            if (code.isBlank() || !codes.contains(code)) {
                throw invalid("lineage references unknown metricCode: " + code);
            }
        });
        return List.copyOf(metrics);
    }

    List<MetricDefinitionDto> asDefinitions(List<ManagedMetric> metrics) {
        long id = 1;
        List<MetricDefinitionDto> result = new ArrayList<>();
        for (ManagedMetric metric : metrics) {
            result.add(metric.toDefinition(id++, 1));
        }
        return List.copyOf(result);
    }

    private JsonNode read(String name) {
        try {
            return mapper.readTree(new ClassPathResource(name).getInputStream());
        } catch (IOException e) {
            throw new IllegalStateException("METRIC_CATALOG_RESOURCE_READ_FAILED: " + name, e);
        }
    }

    private String requiredText(JsonNode item, String field) {
        String value = nullableText(item, field);
        if (blank(value)) {
            throw invalid("missing/blank " + field);
        }
        return value;
    }

    private static String nullableText(JsonNode item, String field) {
        JsonNode value = item.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }

    private String writeJson(Object value) {
        try {
            return mapper.writeValueAsString(value);
        } catch (IOException e) {
            throw new IllegalStateException("METRIC_CATALOG_SERIALIZE_FAILED", e);
        }
    }

    private static boolean blank(String value) {
        return value == null || value.isBlank();
    }

    private static IllegalArgumentException invalid(String reason) {
        return new IllegalArgumentException("METRIC_CATALOG_INVALID: " + reason);
    }

    public record ManagedMetric(
            String metricName,
            String metricCode,
            String businessDefinition,
            String formula,
            String dimensions,
            String timeGranularity,
            String sourceTable,
            String timeField,
            String factFormula,
            String factEventFilter) {

        MetricDefinitionDto toDefinition(long id, int version) {
            return new MetricDefinitionDto(id, metricName, metricCode, businessDefinition, formula,
                    dimensions, timeGranularity, sourceTable, timeField, factFormula,
                    factEventFilter, null, version, "ACTIVE");
        }

        boolean managedEquals(MetricDefinitionDto other) {
            if (other == null) {
                return false;
            }
            return java.util.Objects.equals(metricName, other.metricName())
                    && java.util.Objects.equals(metricCode, other.metricCode())
                    && java.util.Objects.equals(businessDefinition, other.businessDefinition())
                    && java.util.Objects.equals(formula, other.formula())
                    && java.util.Objects.equals(
                            canonicalDimensions(dimensions), canonicalDimensions(other.dimensions()))
                    && java.util.Objects.equals(timeGranularity, other.timeGranularity())
                    && java.util.Objects.equals(sourceTable, other.sourceTable())
                    && java.util.Objects.equals(timeField, other.timeField())
                    && java.util.Objects.equals(factFormula, other.factFormula())
                    && java.util.Objects.equals(factEventFilter, other.factEventFilter())
                    && "ACTIVE".equals(other.status());
        }

        private static String canonicalDimensions(String value) {
            return value == null ? "[]" : value.replaceAll("\\s+", "");
        }
    }
}
