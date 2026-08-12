package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.dto.RelevantSchemaRequest;
import com.yunzhu.video_data_analysis.dto.RelevantSchemaResponse;
import com.yunzhu.video_data_analysis.service.SchemaCatalogService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Internal metadata endpoint used by the LangGraph Agent Engine. */
@RestController
@RequestMapping("/internal/schema")
public class InternalSchemaController {

    private final SchemaCatalogService schemaCatalogService;

    public InternalSchemaController(SchemaCatalogService schemaCatalogService) {
        this.schemaCatalogService = schemaCatalogService;
    }

    @PostMapping("/relevant")
    public RelevantSchemaResponse relevant(@RequestBody RelevantSchemaRequest request) {
        return new RelevantSchemaResponse(schemaCatalogService.relevantSchema(request.question()));
    }
}
