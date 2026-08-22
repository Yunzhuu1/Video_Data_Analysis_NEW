package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.dto.MetricDefinitionDto;
import com.yunzhu.video_data_analysis.semantic.TableSchemaRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.SimpleTransactionStatus;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class MetricCatalogSynchronizerTest {

    private final ObjectMapper mapper = new ObjectMapper();
    private final MetricCatalogResource resource =
            new MetricCatalogResource(mapper, new TableSchemaRegistry());

    @Test
    void oldSevenUpgradeToFifteenAndSecondRunIsIdempotent() {
        List<MetricCatalogResource.ManagedMetric> managed = resource.load();
        InMemoryCatalog catalog = new InMemoryCatalog(resource.asDefinitions(managed.subList(0, 7)));
        MetricCatalogRuntimeState state = new MetricCatalogRuntimeState();
        MetricCatalogSynchronizer synchronizer = synchronizer(catalog, state);

        var first = synchronizer.reconcile();
        assertThat(first.status()).isEqualTo("READY");
        assertThat(first.managedCount()).isEqualTo(15);
        assertThat(catalog.listAll()).hasSize(15);
        Map<String, Integer> versions = catalog.versions();

        var second = synchronizer.reconcile();
        assertThat(second.managedCatalogHash()).isEqualTo(first.managedCatalogHash());
        assertThat(catalog.versions()).isEqualTo(versions);
        assertThat(state.current()).isEqualTo(second);
    }

    @Test
    void changedManagedFieldIncrementsOnlyThatVersionAndExtraIsPreserved() {
        List<MetricCatalogResource.ManagedMetric> managed = resource.load();
        List<MetricDefinitionDto> initial = new ArrayList<>(resource.asDefinitions(managed));
        MetricDefinitionDto first = initial.get(0);
        initial.set(0, new MetricDefinitionDto(first.id(), first.metricName(), first.metricCode(),
                first.businessDefinition(), "stale_formula", first.dimensions(), first.timeGranularity(),
                first.sourceTable(), first.timeField(), first.factFormula(), first.factEventFilter(),
                "human-owner", 4, "ACTIVE"));
        initial.add(new MetricDefinitionDto(999L, "额外指标", "custom_extra", "custom", "COUNT(*)",
                "[]", "day", "metric_daily", "date", null, null,
                "human-owner", 9, "ACTIVE"));
        InMemoryCatalog catalog = new InMemoryCatalog(initial);

        var status = synchronizer(catalog, new MetricCatalogRuntimeState()).reconcile();

        assertThat(status.extraCodes()).containsExactly("custom_extra");
        assertThat(catalog.byCode("custom_extra").owner()).isEqualTo("human-owner");
        assertThat(catalog.byCode(first.metricCode()).formula()).isEqualTo(first.formula());
        assertThat(catalog.byCode(first.metricCode()).owner()).isEqualTo("human-owner");
        assertThat(catalog.byCode(first.metricCode()).version()).isEqualTo(5);
        assertThat(catalog.byCode(managed.get(1).metricCode()).version()).isEqualTo(1);
    }

    private MetricCatalogSynchronizer synchronizer(
            InMemoryCatalog catalog, MetricCatalogRuntimeState state) {
        return new MetricCatalogSynchronizer(
                new TransactionTemplate(new NoOpTransactionManager()),
                resource, catalog, state, mapper);
    }

    private static final class InMemoryCatalog extends MetricCatalogService {
        private final Map<String, MetricDefinitionDto> rows = new LinkedHashMap<>();
        private long nextId = 1000;

        InMemoryCatalog(List<MetricDefinitionDto> initial) {
            super(null);
            initial.forEach(item -> rows.put(item.metricCode(), item));
        }

        @Override
        public List<MetricDefinitionDto> listAll() {
            return rows.values().stream().filter(item -> "ACTIVE".equals(item.status())).toList();
        }

        @Override
        public List<MetricDefinitionDto> listAllIncludingInactive() {
            return List.copyOf(rows.values());
        }

        @Override
        public void insertManaged(MetricCatalogResource.ManagedMetric metric) {
            rows.put(metric.metricCode(), metric.toDefinition(nextId++, 1));
        }

        @Override
        public void updateManaged(MetricCatalogResource.ManagedMetric metric) {
            MetricDefinitionDto old = rows.get(metric.metricCode());
            MetricDefinitionDto updated = metric.toDefinition(old.id(), old.version() + 1);
            rows.put(metric.metricCode(), new MetricDefinitionDto(
                    updated.id(), updated.metricName(), updated.metricCode(), updated.businessDefinition(),
                    updated.formula(), updated.dimensions(), updated.timeGranularity(), updated.sourceTable(),
                    updated.timeField(), updated.factFormula(), updated.factEventFilter(), old.owner(),
                    updated.version(), updated.status()));
        }

        MetricDefinitionDto byCode(String code) {
            return rows.get(code);
        }

        Map<String, Integer> versions() {
            Map<String, Integer> result = new LinkedHashMap<>();
            rows.forEach((code, row) -> result.put(code, row.version()));
            return result;
        }
    }

    private static final class NoOpTransactionManager implements PlatformTransactionManager {
        @Override
        public TransactionStatus getTransaction(TransactionDefinition definition) {
            return new SimpleTransactionStatus();
        }

        @Override
        public void commit(TransactionStatus status) {
        }

        @Override
        public void rollback(TransactionStatus status) {
        }
    }
}
