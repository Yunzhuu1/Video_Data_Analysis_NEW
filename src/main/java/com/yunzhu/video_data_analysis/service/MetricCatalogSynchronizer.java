package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.dto.MetricCatalogRuntimeStatus;
import com.yunzhu.video_data_analysis.dto.MetricDefinitionDto;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 将 classpath 权威指标目录事务性 reconciliation 到 metric_definition。 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
@ConditionalOnProperty(prefix = "app.metric-catalog-sync", name = "enabled",
        havingValue = "true")
public class MetricCatalogSynchronizer implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(MetricCatalogSynchronizer.class);

    private final TransactionTemplate transactions;
    private final MetricCatalogResource resource;
    private final MetricCatalogService catalog;
    private final MetricCatalogRuntimeState runtimeState;
    private final ObjectMapper mapper;

    public MetricCatalogSynchronizer(
            TransactionTemplate transactions,
            MetricCatalogResource resource,
            MetricCatalogService catalog,
            MetricCatalogRuntimeState runtimeState,
            ObjectMapper mapper) {
        this.transactions = transactions;
        this.resource = resource;
        this.catalog = catalog;
        this.runtimeState = runtimeState;
        this.mapper = mapper;
    }

    @Override
    public void run(ApplicationArguments args) {
        reconcile();
    }

    public MetricCatalogRuntimeStatus reconcile() {
        List<MetricCatalogResource.ManagedMetric> managed = resource.load();
        try {
            MetricCatalogRuntimeStatus status = transactions.execute(tx -> reconcileInTransaction(managed));
            if (status == null) {
                throw new IllegalStateException("METRIC_CATALOG_SYNC_FAILED: transaction returned no status");
            }
            runtimeState.publish(status);
            log.info("Metric catalog READY: managed={}, active={}, extra={}, hash={}",
                    status.managedCount(), status.activeCount(), status.extraCodes().size(),
                    status.runtimeCatalogHash());
            return status;
        } catch (RuntimeException e) {
            log.error("Metric catalog reconciliation failed; refusing startup", e);
            throw e;
        }
    }

    private MetricCatalogRuntimeStatus reconcileInTransaction(
            List<MetricCatalogResource.ManagedMetric> managed) {
        Map<String, MetricDefinitionDto> existing = new HashMap<>();
        for (MetricDefinitionDto definition : catalog.listAllIncludingInactive()) {
            existing.put(definition.metricCode(), definition);
        }
        List<String> changed = new ArrayList<>();
        for (MetricCatalogResource.ManagedMetric metric : managed) {
            MetricDefinitionDto current = existing.get(metric.metricCode());
            if (current == null) {
                insert(metric);
                changed.add(metric.metricCode());
            } else if (!metric.managedEquals(current)) {
                update(metric);
                changed.add(metric.metricCode());
            }
        }

        List<MetricDefinitionDto> active = catalog.listAll();
        Set<String> managedCodes = new HashSet<>();
        managed.forEach(metric -> managedCodes.add(metric.metricCode()));
        Map<String, MetricDefinitionDto> activeByCode = new HashMap<>();
        active.forEach(metric -> activeByCode.put(metric.metricCode(), metric));

        List<String> missing = managedCodes.stream()
                .filter(code -> !activeByCode.containsKey(code)).sorted().toList();
        List<String> drifted = managed.stream()
                .filter(metric -> activeByCode.containsKey(metric.metricCode()))
                .filter(metric -> !metric.managedEquals(activeByCode.get(metric.metricCode())))
                .map(MetricCatalogResource.ManagedMetric::metricCode).sorted().toList();
        List<String> extra = active.stream().map(MetricDefinitionDto::metricCode)
                .filter(code -> !managedCodes.contains(code)).sorted().toList();

        List<MetricDefinitionDto> resourceDefinitions = resource.asDefinitions(managed);
        List<MetricDefinitionDto> managedReadBack = managedCodes.stream()
                .map(activeByCode::get).filter(java.util.Objects::nonNull).toList();
        String expectedHash = MetricCatalogProjection.hash(mapper, resourceDefinitions);
        String actualManagedHash = MetricCatalogProjection.hash(mapper, managedReadBack);
        if (!missing.isEmpty() || !drifted.isEmpty() || !expectedHash.equals(actualManagedHash)) {
            throw new IllegalStateException("METRIC_CATALOG_SYNC_MISMATCH: missing=" + missing
                    + ", drifted=" + drifted + ", expectedHash=" + expectedHash
                    + ", actualHash=" + actualManagedHash);
        }
        if (!extra.isEmpty()) {
            log.warn("Metric catalog contains unmanaged ACTIVE codes (preserved): {}", extra);
        }
        if (!changed.isEmpty()) {
            log.info("Metric catalog inserted/updated managed codes: {}", changed);
        }
        return new MetricCatalogRuntimeStatus(
                "READY", managed.size(), active.size(), expectedHash,
                MetricCatalogProjection.hash(mapper, active),
                List.copyOf(missing), List.copyOf(drifted), List.copyOf(extra));
    }

    private void insert(MetricCatalogResource.ManagedMetric metric) {
        catalog.insertManaged(metric);
    }

    private void update(MetricCatalogResource.ManagedMetric metric) {
        catalog.updateManaged(metric);
    }
}
