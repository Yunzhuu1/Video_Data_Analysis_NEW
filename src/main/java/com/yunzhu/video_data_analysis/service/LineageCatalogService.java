package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.yunzhu.video_data_analysis.dto.LineageSnapshotDto;
import com.yunzhu.video_data_analysis.dto.MetricDefinitionDto;
import com.yunzhu.video_data_analysis.semantic.TableSchemaRegistry;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 加载并校验 Git 版本化 lineage overlay，发布组合不可变快照。 */
@Service
public class LineageCatalogService {

    private final ObjectMapper mapper;
    private final TableSchemaRegistry schemas;
    private final MetricCatalogService metrics;
    private final JsonNode lineage;

    public LineageCatalogService(ObjectMapper mapper, TableSchemaRegistry schemas,
                                 MetricCatalogService metrics) {
        this.mapper = mapper;
        this.schemas = schemas;
        this.metrics = metrics;
        this.lineage = loadResource(mapper, "lineage_catalog.json");
        validate(lineage, schemas, null);
    }

    public LineageSnapshotDto snapshot() {
        return buildSnapshot(metrics.listAll());
    }

    LineageSnapshotDto buildSnapshot(List<MetricDefinitionDto> definitions) {
        validate(lineage, schemas, definitions.stream().map(MetricDefinitionDto::metricCode).collect(
                java.util.stream.Collectors.toSet()));
        List<Map<String, Object>> normalized = MetricCatalogProjection.normalize(mapper, definitions);
        Map<String, List<String>> projection = schemaProjection();
        JsonNode metricNode = mapper.valueToTree(normalized);
        JsonNode schemaNode = mapper.valueToTree(projection);
        String lineageHash = CanonicalJson.sha256(mapper, lineage);
        String metricHash = CanonicalJson.sha256(mapper, metricNode);
        String schemaHash = CanonicalJson.sha256(mapper, schemaNode);
        ObjectNode combined = mapper.createObjectNode();
        combined.set("lineage", lineage);
        combined.set("metrics", metricNode);
        combined.set("schema", schemaNode);
        return new LineageSnapshotDto(CanonicalJson.sha256(mapper, combined), lineageHash,
                metricHash, schemaHash, lineage.deepCopy(), List.copyOf(normalized),
                java.util.Collections.unmodifiableMap(projection));
    }

    private Map<String, List<String>> schemaProjection() {
        Set<String> tableNames = new HashSet<>();
        lineage.path("tables").forEach(item -> tableNames.add(item.path("tableName").asText()));
        Map<String, List<String>> result = new java.util.TreeMap<>();
        for (String table : tableNames) {
            result.put(table, schemas.columnsOf(table).stream().sorted().toList());
        }
        return result;
    }

    static void validate(JsonNode catalog, TableSchemaRegistry schemas, Set<String> metricCodes) {
        unique(catalog.path("tables"), "tableName");
        unique(catalog.path("metricPaths"), "pathId");
        unique(catalog.path("dimensionBindings"), "bindingId");
        unique(catalog.path("joinEdges"), "edgeId");
        catalog.path("tables").forEach(item -> requireTable(schemas, item.path("tableName").asText()));
        catalog.path("metricPaths").forEach(item -> {
            requireTable(schemas, item.path("sourceTable").asText());
            requireColumn(schemas, item.path("sourceTable").asText(), item.path("timeFieldRef").asText());
            if (metricCodes != null && !metricCodes.contains(item.path("metricCode").asText())) {
                throw new IllegalArgumentException("unknown metricCode in path " + item.path("pathId").asText());
            }
        });
        catalog.path("dimensionBindings").forEach(item -> {
            String table = item.path("tableName").asText();
            requireColumn(schemas, table, item.path("keyColumn").asText());
            requireColumn(schemas, table, item.path("labelColumn").asText());
        });
        catalog.path("joinEdges").forEach(item -> {
            validateColumns(schemas, item, "fromTable", "fromColumns");
            validateColumns(schemas, item, "toTable", "toColumns");
            if (!Set.of("N:1", "1:1").contains(item.path("cardinalityFromTo").asText())) {
                throw new IllegalArgumentException("unsafe cardinality on edge " + item.path("edgeId").asText());
            }
            if (item.path("fromColumns").size() != item.path("toColumns").size()) {
                throw new IllegalArgumentException("join column count mismatch on " + item.path("edgeId").asText());
            }
        });
    }

    private static void unique(JsonNode array, String field) {
        Set<String> ids = new HashSet<>();
        array.forEach(item -> {
            String id = item.path(field).asText();
            if (id.isBlank() || !ids.add(id)) {
                throw new IllegalArgumentException("duplicate/empty " + field + ": " + id);
            }
        });
    }

    private static void validateColumns(TableSchemaRegistry schemas, JsonNode item,
                                        String tableField, String columnsField) {
        String table = item.path(tableField).asText();
        requireTable(schemas, table);
        item.path(columnsField).forEach(column -> requireColumn(schemas, table, column.asText()));
    }

    private static void requireTable(TableSchemaRegistry schemas, String table) {
        if (!schemas.hasTable(table)) {
            throw new IllegalArgumentException("unknown table: " + table);
        }
    }

    private static void requireColumn(TableSchemaRegistry schemas, String table, String column) {
        requireTable(schemas, table);
        if (!schemas.hasColumn(table, column)) {
            throw new IllegalArgumentException("unknown column: " + table + "." + column);
        }
    }

    private static JsonNode loadResource(ObjectMapper mapper, String name) {
        try {
            return mapper.readTree(new ClassPathResource(name).getInputStream());
        } catch (IOException e) {
            throw new IllegalStateException("failed to load " + name, e);
        }
    }
}
