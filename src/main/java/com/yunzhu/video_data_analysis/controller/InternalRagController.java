package com.yunzhu.video_data_analysis.controller;

import com.yunzhu.video_data_analysis.agent.RAGAgent;
import com.yunzhu.video_data_analysis.dto.CommentResult;
import com.yunzhu.video_data_analysis.dto.RagAnalyzeRequest;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Internal RAG endpoint used by the LangGraph Agent Engine. */
@RestController
@RequestMapping("/internal/rag")
public class InternalRagController {

    private final RAGAgent ragAgent;

    public InternalRagController(RAGAgent ragAgent) {
        this.ragAgent = ragAgent;
    }

    @PostMapping("/analyze")
    public CommentResult analyze(@RequestBody RagAnalyzeRequest request) {
        return ragAgent.analyze(request.question(), request.queryResult());
    }
}
