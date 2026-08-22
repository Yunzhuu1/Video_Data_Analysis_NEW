package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.dto.MetricDefinitionDto;
import com.yunzhu.video_data_analysis.dto.MetricCatalogRuntimeStatus;
import com.yunzhu.video_data_analysis.service.MetricCatalogService;
import com.yunzhu.video_data_analysis.service.MetricCatalogRuntimeState;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** 内部指标字典接口，供 LangGraph Agent Engine 语义解析/合成使用。 */
@RestController
@RequestMapping("/internal/metrics")
public class InternalMetricController {

    private final MetricCatalogService metricCatalogService;
    private final MetricCatalogRuntimeState runtimeState;

    public InternalMetricController(MetricCatalogService metricCatalogService,
                                    MetricCatalogRuntimeState runtimeState) {
        this.metricCatalogService = metricCatalogService;
        this.runtimeState = runtimeState;
    }

    @GetMapping("/runtime-status")
    public MetricCatalogRuntimeStatus runtimeStatus() {
        return runtimeState.current();
    }

    @GetMapping
    public List<MetricDefinitionDto> list(@RequestParam(required = false) String keyword) {
        return keyword == null || keyword.isBlank()
                ? metricCatalogService.listAll()
                : metricCatalogService.search(keyword);
    }

    @GetMapping("/{code}")
    public MetricDefinitionDto byCode(@PathVariable String code) {
        MetricDefinitionDto dto = metricCatalogService.findByCode(code);
        if (dto == null) {
            throw new IllegalArgumentException("metric not found: " + code);
        }
        return dto;
    }
}
