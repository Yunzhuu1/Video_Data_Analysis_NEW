package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.AgentRunDetail;
import com.yunzhu.video_data_analysis.dto.AgentRunNodeDetail;
import com.yunzhu.video_data_analysis.dto.AgentRunSummary;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/** Read-side service for Agent Run operation views. */
@Service
public class AgentRunQueryService {

    private final JdbcTemplate jdbcTemplate;
    private final AgentRunTraceService traceService;

    public AgentRunQueryService(JdbcTemplate jdbcTemplate, AgentRunTraceService traceService) {
        this.jdbcTemplate = jdbcTemplate;
        this.traceService = traceService;
    }

    public List<AgentRunSummary> listRecentRuns(int limit) {
        traceService.ensureTables();
        int safeLimit = Math.max(1, Math.min(limit, 100));
        return jdbcTemplate.query("""
                SELECT run_id, user_id, question, status, current_node, error_message,
                       started_at, finished_at, total_duration_ms
                FROM agent_run
                ORDER BY started_at DESC
                LIMIT ?
                """, (rs, rowNum) -> new AgentRunSummary(
                rs.getString("run_id"),
                rs.getString("user_id"),
                rs.getString("question"),
                rs.getString("status"),
                rs.getString("current_node"),
                rs.getString("error_message"),
                toLocalDateTime(rs.getTimestamp("started_at")),
                toLocalDateTime(rs.getTimestamp("finished_at")),
                getLong(rs.getObject("total_duration_ms"))
        ), safeLimit);
    }

    public AgentRunDetail getRunDetail(String runId) {
        traceService.ensureTables();
        Map<String, Object> run = jdbcTemplate.queryForMap("""
                SELECT run_id, user_id, question, status, current_node, final_report, error_message,
                       started_at, finished_at, total_duration_ms
                FROM agent_run
                WHERE run_id = ?
                """, runId);
        return new AgentRunDetail(
                (String) run.get("run_id"),
                (String) run.get("user_id"),
                (String) run.get("question"),
                (String) run.get("status"),
                (String) run.get("current_node"),
                (String) run.get("final_report"),
                (String) run.get("error_message"),
                toLocalDateTime((Timestamp) run.get("started_at")),
                toLocalDateTime((Timestamp) run.get("finished_at")),
                getLong(run.get("total_duration_ms")),
                listRunNodes(runId)
        );
    }

    public List<AgentRunNodeDetail> listRunNodes(String runId) {
        traceService.ensureTables();
        return jdbcTemplate.query("""
                SELECT id, node_name, status, input_payload, output_payload, error_message,
                       model_name, prompt_tokens, completion_tokens, duration_ms, retry_count,
                       started_at, finished_at
                FROM agent_run_node
                WHERE run_id = ?
                ORDER BY id ASC
                """, (rs, rowNum) -> new AgentRunNodeDetail(
                rs.getLong("id"),
                rs.getString("node_name"),
                rs.getString("status"),
                rs.getString("input_payload"),
                rs.getString("output_payload"),
                rs.getString("error_message"),
                rs.getString("model_name"),
                rs.getInt("prompt_tokens"),
                rs.getInt("completion_tokens"),
                getLong(rs.getObject("duration_ms")),
                rs.getInt("retry_count"),
                toLocalDateTime(rs.getTimestamp("started_at")),
                toLocalDateTime(rs.getTimestamp("finished_at"))
        ), runId);
    }

    private static LocalDateTime toLocalDateTime(Timestamp ts) {
        return ts == null ? null : ts.toLocalDateTime();
    }

    private static Long getLong(Object value) {
        return value instanceof Number n ? n.longValue() : null;
    }
}
