package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.MetricCatalogRuntimeStatus;
import org.springframework.stereotype.Component;

/** 进程内只读目录状态；仅 Synchronizer 发布新快照。 */
@Component
public class MetricCatalogRuntimeState {

    private volatile MetricCatalogRuntimeStatus current = MetricCatalogRuntimeStatus.notStarted();

    public MetricCatalogRuntimeStatus current() {
        return current;
    }

    void publish(MetricCatalogRuntimeStatus status) {
        this.current = status;
    }
}
