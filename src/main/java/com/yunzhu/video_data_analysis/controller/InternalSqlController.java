package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.dto.SqlExecuteRequest;
import com.yunzhu.video_data_analysis.dto.SqlExecuteResult;
import com.yunzhu.video_data_analysis.dto.SqlGateResult;
import com.yunzhu.video_data_analysis.dto.SqlValidateRequest;
import com.yunzhu.video_data_analysis.service.SqlExecutionService;
import com.yunzhu.video_data_analysis.service.SqlGateService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Internal SQL gateway endpoint for future LangGraph Agent Engine calls. */
@RestController
@RequestMapping("/internal/sql")
public class InternalSqlController {

    private final SqlExecutionService sqlExecutionService;
    private final SqlGateService sqlGateService;

    public InternalSqlController(SqlExecutionService sqlExecutionService,
                                 SqlGateService sqlGateService) {
        this.sqlExecutionService = sqlExecutionService;
        this.sqlGateService = sqlGateService;
    }

    @PostMapping("/execute")
    public SqlExecuteResult execute(@RequestBody SqlExecuteRequest request) {
        return sqlExecutionService.execute(request);
    }

    @PostMapping("/validate")
    public SqlGateResult validate(@RequestBody SqlValidateRequest request) {
        return sqlGateService.evaluate(request.sql(), request.allowHighRisk(),
                request.intent(), request.intentTimeRangeType());
    }
}
