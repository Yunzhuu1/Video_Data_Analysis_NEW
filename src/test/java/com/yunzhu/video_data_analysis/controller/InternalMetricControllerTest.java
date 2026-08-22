package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.dto.MetricCatalogRuntimeStatus;
import com.yunzhu.video_data_analysis.service.MetricCatalogRuntimeState;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class InternalMetricControllerTest {

    @Test
    void runtimeStatusDoesNotExposeMetricFormulaOrPath() {
        MetricCatalogRuntimeState state = new MetricCatalogRuntimeState();
        InternalMetricController controller = new InternalMetricController(null, state);

        MetricCatalogRuntimeStatus status = controller.runtimeStatus();

        assertThat(status.status()).isEqualTo("NOT_STARTED");
        assertThat(status.managedCatalogHash()).isNull();
        assertThat(status.missingCodes()).isEmpty();
    }
}
