package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.dto.SqlDQCheckRequest;
import com.yunzhu.video_data_analysis.dto.SqlDQCheckResult;
import com.yunzhu.video_data_analysis.service.SqlResultDQService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Internal DQ endpoint for checking SQL result usefulness. */
@RestController
@RequestMapping("/internal/dq")
public class InternalDQController {

    private final SqlResultDQService sqlResultDQService;

    public InternalDQController(SqlResultDQService sqlResultDQService) {
        this.sqlResultDQService = sqlResultDQService;
    }

    @PostMapping("/sql-result/check")
    public SqlDQCheckResult checkSqlResult(@RequestBody SqlDQCheckRequest request) {
        return sqlResultDQService.check(request);
    }
}
