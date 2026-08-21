package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.dto.LineageSnapshotDto;
import com.yunzhu.video_data_analysis.service.LineageCatalogService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Agent Engine 使用的只读血缘快照接口。 */
@RestController
@RequestMapping("/internal/lineage")
public class InternalLineageController {

    private final LineageCatalogService service;

    public InternalLineageController(LineageCatalogService service) {
        this.service = service;
    }

    @GetMapping("/snapshot")
    public LineageSnapshotDto snapshot() {
        return service.snapshot();
    }
}
