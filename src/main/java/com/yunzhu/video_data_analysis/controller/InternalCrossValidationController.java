package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.dto.CrossValidationRequest;
import com.yunzhu.video_data_analysis.dto.CrossValidationResponse;
import com.yunzhu.video_data_analysis.service.CrossValidationService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Internal cross-validation endpoint used by the LangGraph Agent Engine. */
@RestController
@RequestMapping("/internal/cross-validation")
public class InternalCrossValidationController {

    private final CrossValidationService crossValidationService;

    public InternalCrossValidationController(CrossValidationService crossValidationService) {
        this.crossValidationService = crossValidationService;
    }

    @PostMapping("/analyze")
    public CrossValidationResponse analyze(@RequestBody CrossValidationRequest request) {
        return new CrossValidationResponse(crossValidationService.crossValidate(request.ragResult()));
    }
}
