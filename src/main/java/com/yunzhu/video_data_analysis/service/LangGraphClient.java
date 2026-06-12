package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.dto.EngineAnalyzeRequest;
import com.yunzhu.video_data_analysis.dto.EngineAnalyzeResponse;
import com.yunzhu.video_data_analysis.dto.EngineApprovalRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/** Client for the Python LangGraph Agent Engine. */
@Service
public class LangGraphClient {

    private final String baseUrl;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    public LangGraphClient(@Value("${app.langgraph.base-url:http://localhost:8090}") String baseUrl,
                           ObjectMapper objectMapper) {
        this.baseUrl = stripTrailingSlash(baseUrl);
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(5))
                .build();
        this.objectMapper = objectMapper;
    }

    public EngineAnalyzeResponse analyze(EngineAnalyzeRequest request) {
        return post("/analyze", request);
    }

    public EngineAnalyzeResponse approve(String runId, boolean approved) {
        return post("/runs/" + runId + "/approval", new EngineApprovalRequest(approved));
    }

    private EngineAnalyzeResponse post(String path, Object body) {
        String json = toJson(body);
        HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + path))
                .timeout(Duration.ofSeconds(90))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json))
                .build();
        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                throw new IllegalStateException("LangGraph request failed: HTTP "
                        + response.statusCode() + " " + response.body());
            }
            return objectMapper.readValue(response.body(), EngineAnalyzeResponse.class);
        } catch (IOException e) {
            throw new IllegalStateException("LangGraph request failed", e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("LangGraph request interrupted", e);
        }
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("Failed to serialize LangGraph request", e);
        }
    }

    private static String stripTrailingSlash(String value) {
        if (value == null || value.isBlank()) {
            return "http://localhost:8090";
        }
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }
}
