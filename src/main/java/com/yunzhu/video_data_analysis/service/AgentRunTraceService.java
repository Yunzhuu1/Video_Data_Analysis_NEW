package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.model.NodeStatus;
import com.yunzhu.video_data_analysis.model.RunStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Service;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

/** Persists analysis run and node lifecycle events for operation visibility. */
@Service
public class AgentRunTraceService {

    private static final Logger log = LoggerFactory.getLogger(AgentRunTraceService.class);
    private static final int PAYLOAD_LIMIT = 20_000;

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;
    private final AtomicBoolean tablesReady = new AtomicBoolean(false);

    public AgentRunTraceService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public String startRun(String userId, String question) {
        ensureTables();
        String runId = "run_" + UUID.randomUUID();
        jdbcTemplate.update("""
                INSERT INTO agent_run(run_id, user_id, question, status, started_at)
                VALUES (?, ?, ?, ?, NOW())
                """, runId, userId, question, RunStatus.RUNNING.name());
        return runId;
    }

    public Long startNode(String runId, String nodeName, Object inputPayload) {
        ensureTables();
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement ps = connection.prepareStatement("""
                    INSERT INTO agent_run_node(run_id, node_name, status, input_payload, started_at)
                    VALUES (?, ?, ?, ?, NOW())
                    """, Statement.RETURN_GENERATED_KEYS);
            ps.setString(1, runId);
            ps.setString(2, nodeName);
            ps.setString(3, NodeStatus.RUNNING.name());
            ps.setString(4, toPayload(inputPayload));
            return ps;
        }, keyHolder);
        jdbcTemplate.update("UPDATE agent_run SET current_node = ? WHERE run_id = ?", nodeName, runId);
        Number key = keyHolder.getKey();
        return key != null ? key.longValue() : null;
    }

    public void finishNode(Long nodeId, Object outputPayload) {
        if (nodeId == null) return;
        ensureTables();
        jdbcTemplate.update("""
                UPDATE agent_run_node
                SET status = ?, output_payload = ?, duration_ms = TIMESTAMPDIFF(MICROSECOND, started_at, NOW()) DIV 1000,
                    finished_at = NOW()
                WHERE id = ?
                """, NodeStatus.SUCCESS.name(), toPayload(outputPayload), nodeId);
    }

    public void failNode(Long nodeId, Throwable error) {
        failNode(nodeId, error != null ? error.getMessage() : "Unknown error");
    }

    public void failNode(Long nodeId, String errorMessage) {
        if (nodeId == null) return;
        ensureTables();
        jdbcTemplate.update("""
                UPDATE agent_run_node
                SET status = ?, error_message = ?, duration_ms = TIMESTAMPDIFF(MICROSECOND, started_at, NOW()) DIV 1000,
                    finished_at = NOW()
                WHERE id = ?
                """, NodeStatus.FAILED.name(), truncate(errorMessage), nodeId);
    }

    public void skipNode(String runId, String nodeName, String reason) {
        ensureTables();
        jdbcTemplate.update("""
                INSERT INTO agent_run_node(run_id, node_name, status, error_message, started_at, finished_at, duration_ms)
                VALUES (?, ?, ?, ?, NOW(), NOW(), 0)
                """, runId, nodeName, NodeStatus.SKIPPED.name(), truncate(reason));
    }

    public void finishRun(String runId, Object finalReport) {
        ensureTables();
        jdbcTemplate.update("""
                UPDATE agent_run
                SET status = ?, final_report = ?, finished_at = NOW(),
                    total_duration_ms = TIMESTAMPDIFF(MICROSECOND, started_at, NOW()) DIV 1000
                WHERE run_id = ?
                """, RunStatus.SUCCESS.name(), toPayload(finalReport), runId);
    }

    public void waitForApprovalRun(String runId, String reason) {
        ensureTables();
        jdbcTemplate.update("""
                UPDATE agent_run
                SET status = ?, current_node = ?, error_message = ?
                WHERE run_id = ?
                """, RunStatus.WAITING_APPROVAL.name(), "HUMAN_APPROVAL", truncate(reason), runId);
    }

    public void failRun(String runId, Throwable error) {
        ensureTables();
        jdbcTemplate.update("""
                UPDATE agent_run
                SET status = ?, error_message = ?, finished_at = NOW(),
                    total_duration_ms = TIMESTAMPDIFF(MICROSECOND, started_at, NOW()) DIV 1000
                WHERE run_id = ?
                """, RunStatus.FAILED.name(), truncate(error != null ? error.getMessage() : "Unknown error"), runId);
    }

    public void ensureTables() {
        if (tablesReady.get()) return;
        synchronized (tablesReady) {
            if (tablesReady.get()) return;
            jdbcTemplate.execute("""
                    CREATE TABLE IF NOT EXISTS agent_run (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        run_id VARCHAR(64) NOT NULL UNIQUE,
                        user_id VARCHAR(64) NOT NULL,
                        question TEXT NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        current_node VARCHAR(64),
                        final_report LONGTEXT,
                        error_message TEXT,
                        started_at DATETIME NOT NULL,
                        finished_at DATETIME,
                        total_duration_ms BIGINT,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_user_created (user_id, created_at),
                        INDEX idx_status_created (status, created_at)
                    )
                    """);
            jdbcTemplate.execute("""
                    CREATE TABLE IF NOT EXISTS agent_run_node (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        run_id VARCHAR(64) NOT NULL,
                        node_name VARCHAR(64) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        input_payload MEDIUMTEXT,
                        output_payload MEDIUMTEXT,
                        error_message TEXT,
                        model_name VARCHAR(128),
                        prompt_tokens INT DEFAULT 0,
                        completion_tokens INT DEFAULT 0,
                        duration_ms BIGINT,
                        retry_count INT DEFAULT 0,
                        started_at DATETIME,
                        finished_at DATETIME,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_run_id (run_id),
                        INDEX idx_node_status (node_name, status),
                        INDEX idx_created_at (created_at)
                    )
                    """);
            tablesReady.set(true);
        }
    }

    private String toPayload(Object value) {
        if (value == null) return null;
        try {
            return truncate(objectMapper.writeValueAsString(value));
        } catch (Exception e) {
            log.debug("Failed to serialize run payload", e);
            return truncate(String.valueOf(value));
        }
    }

    private static String truncate(String value) {
        if (value == null || value.length() <= PAYLOAD_LIMIT) return value;
        return value.substring(0, PAYLOAD_LIMIT) + "...[truncated]";
    }
}
