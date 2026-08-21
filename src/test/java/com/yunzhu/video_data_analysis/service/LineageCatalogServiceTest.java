package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.dto.LineageSnapshotDto;
import com.yunzhu.video_data_analysis.dto.MetricDefinitionDto;
import com.yunzhu.video_data_analysis.semantic.TableSchemaRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;

class LineageCatalogServiceTest {

    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void canonicalFixtureMatchesPythonExpectedHash() throws Exception {
        JsonNode fixture = mapper.readTree(new ClassPathResource("canonical_hash_fixture.json").getInputStream());
        String expected = new String(
                new ClassPathResource("canonical_hash_fixture.sha256").getInputStream().readAllBytes(),
                StandardCharsets.UTF_8).trim();
        assertThat(CanonicalJson.sha256(mapper, fixture)).isEqualTo(expected);
        assertThat(CanonicalJson.string(mapper, fixture)).startsWith("{\"array\"");
    }

    @Test
    void snapshotFreezesMetricsAndMetricChangeInvalidatesVersion() {
        LineageCatalogService service = new LineageCatalogService(
                mapper, new TableSchemaRegistry(), mock(MetricCatalogService.class));
        MetricDefinitionDto first = metric("total_plays", "total_plays");
        MetricDefinitionDto changed = metric("total_plays", "SUM(total_plays)");
        MetricDefinitionDto likes = metric("total_likes", "total_likes");
        MetricDefinitionDto completion = new MetricDefinitionDto(
                3L, "完播率", "completion_rate", "", "AVG(completion_rate)", "[\"content\"]",
                "天", "play_detail", "created_at", null, null, "demo", 1, "ACTIVE");
        MetricDefinitionDto revenue = new MetricDefinitionDto(
                4L, "视频收益", "video_revenue", "", "SUM(revenue)", "[\"content\"]",
                "天", "video_revenue", "stat_date", null, null, "demo", 1, "ACTIVE");
        LineageSnapshotDto a = service.buildSnapshot(List.of(first, likes, completion, revenue));
        LineageSnapshotDto b = service.buildSnapshot(List.of(changed, likes, completion, revenue));
        assertThat(a.lineageHash()).isEqualTo(b.lineageHash());
        assertThat(a.metricCatalogHash()).isNotEqualTo(b.metricCatalogHash());
        assertThat(a.catalogVersion()).isNotEqualTo(b.catalogVersion());
        assertThat(a.schemaProjection()).containsKey("play_detail");
    }

    @Test
    void repositorySnapshotMatchesPythonHashes() throws Exception {
        LineageCatalogService service = new LineageCatalogService(
                mapper, new TableSchemaRegistry(), mock(MetricCatalogService.class));
        JsonNode catalog = mapper.readTree(
                new ClassPathResource("metric_catalog.json").getInputStream());
        List<MetricDefinitionDto> definitions = new java.util.ArrayList<>();
        long id = 1;
        for (JsonNode item : catalog) {
            definitions.add(new MetricDefinitionDto(
                    id++, item.path("metricName").asText(), item.path("metricCode").asText(),
                    item.path("businessDefinition").asText(), item.path("formula").asText(),
                    mapper.writeValueAsString(item.path("dimensions")), item.path("timeGranularity").asText(),
                    item.path("sourceTable").asText(), item.path("timeField").asText(),
                    item.path("factFormula").isNull() ? null : item.path("factFormula").asText(),
                    item.path("factEventFilter").isNull() ? null : item.path("factEventFilter").asText(),
                    "demo", 1, "ACTIVE"));
        }
        LineageSnapshotDto snapshot = service.buildSnapshot(definitions);
        assertThat(snapshot.catalogVersion())
                .isEqualTo("2ed1b7d6dbe10beecc72f7a6f69f4e65bfe56da130e183178214667ad6f7a235");
        assertThat(snapshot.lineageHash())
                .isEqualTo("284d02ccfe1b1c676fb99c207eeac61443c738dc1d3ad45051b38c180edc605a");
        assertThat(snapshot.metricCatalogHash())
                .isEqualTo("91f6f54d0f2aa622b866ee302133ae8212b8064710e88a650670ccd6eb9f08b8");
        assertThat(snapshot.schemaHash())
                .isEqualTo("fa038280eaf7683b9ba032f95282b0a1810a898381e0558c4512436d310636e8");
    }

    @Test
    void unknownPhysicalFieldFailsFast() throws Exception {
        JsonNode catalog = mapper.readTree(new ClassPathResource("lineage_catalog.json").getInputStream());
        ((com.fasterxml.jackson.databind.node.ObjectNode) catalog.path("dimensionBindings").get(0))
                .put("labelColumn", "does_not_exist");
        assertThatThrownBy(() -> LineageCatalogService.validate(
                catalog, new TableSchemaRegistry(), null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("metric_daily.does_not_exist");
    }

    private static MetricDefinitionDto metric(String code, String formula) {
        return new MetricDefinitionDto(1L, code, code, "", formula, "[\"date\",\"category\"]",
                "天", "metric_daily", "date", "COUNT(*)", "event_type = 'play'",
                "demo", 1, "ACTIVE");
    }
}
