package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.dto.SqlExecuteRequest;
import com.yunzhu.video_data_analysis.dto.SqlExecuteResult;
import com.yunzhu.video_data_analysis.dto.SqlValidateRequest;
import com.yunzhu.video_data_analysis.dto.SqlValidateResult;
import com.yunzhu.video_data_analysis.service.SqlExecutionService;
import com.yunzhu.video_data_analysis.service.SqlValidationService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Internal SQL gateway endpoint for future LangGraph Agent Engine calls. */
@RestController
@RequestMapping("/internal/sql")
public class InternalSqlController {

    private final SqlExecutionService sqlExecutionService;
    private final SqlValidationService sqlValidationService;

    public InternalSqlController(SqlExecutionService sqlExecutionService,
                                 SqlValidationService sqlValidationService) {
        this.sqlExecutionService = sqlExecutionService;
        this.sqlValidationService = sqlValidationService;
    }

    @PostMapping("/execute")
    public SqlExecuteResult execute(@RequestBody SqlExecuteRequest request) {
        return sqlExecutionService.execute(request);
    }

    @PostMapping("/validate")
    public SqlValidateResult validate(@RequestBody SqlValidateRequest request) {
        return sqlValidationService.validate(request);
    }
}
