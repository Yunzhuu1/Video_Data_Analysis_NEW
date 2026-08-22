package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.yunzhu.video_data_analysis.semantic.TableSchemaRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MetricCatalogResourceTest {

    private final ObjectMapper mapper = new ObjectMapper();
    private final MetricCatalogResource resource =
            new MetricCatalogResource(mapper, new TableSchemaRegistry());

    @Test
    void repositoryCatalogLoadsFifteenManagedMetrics() {
        var metrics = resource.load();
        assertThat(metrics).hasSize(15);
        assertThat(metrics).extracting(MetricCatalogResource.ManagedMetric::metricCode)
                .contains("comment_rate", "video_revenue", "daily_active_users");
        assertThat(MetricCatalogProjection.hash(mapper, resource.asDefinitions(metrics)))
                .isEqualTo("91f6f54d0f2aa622b866ee302133ae8212b8064710e88a650670ccd6eb9f08b8");
    }

    @Test
    void duplicateCodeFailsWithStableDiagnostic() throws Exception {
        ArrayNode catalog = (ArrayNode) read("metric_catalog.json");
        catalog.add(catalog.get(0).deepCopy());
        assertThatThrownBy(() -> resource.parse(catalog, read("lineage_catalog.json")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("METRIC_CATALOG_INVALID: duplicate metricCode");
    }

    @Test
    void unknownPhysicalTimeFieldFailsFast() throws Exception {
        ArrayNode catalog = (ArrayNode) read("metric_catalog.json");
        ((ObjectNode) catalog.get(0)).put("timeField", "does_not_exist");
        assertThatThrownBy(() -> resource.parse(catalog, read("lineage_catalog.json")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("metric_daily.does_not_exist");
    }

    @Test
    void lineageUnknownMetricFailsFast() throws Exception {
        ObjectNode lineage = (ObjectNode) read("lineage_catalog.json");
        ((ObjectNode) lineage.path("metricPaths").get(0)).put("metricCode", "missing_metric");
        assertThatThrownBy(() -> resource.parse(read("metric_catalog.json"), lineage))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("lineage references unknown metricCode: missing_metric");
    }

    private JsonNode read(String name) throws Exception {
        return mapper.readTree(new ClassPathResource(name).getInputStream());
    }
}
