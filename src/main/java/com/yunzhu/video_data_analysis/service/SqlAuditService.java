package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlExecuteRequest;
import com.yunzhu.video_data_analysis.dto.SqlExecuteResult;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.StringJoiner;
import java.util.concurrent.atomic.AtomicBoolean;

/** Persists SQL execution audit events for platform governance. */
@Service
public class SqlAuditService {

    private final JdbcTemplate jdbcTemplate;
    private final AtomicBoolean tableReady = new AtomicBoolean(false);

    public SqlAuditService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void record(SqlExecuteRequest request, SqlExecuteResult result) {
        ensureTable();
        jdbcTemplate.update("""
                INSERT INTO agent_audit_log(
                    run_id, user_id, action, sql_text, accessed_tables, risk_level, decision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NOW())
                """,
                request.runId(),
                request.userId(),
                "SQL_EXECUTE",
                request.sql(),
                join(result.accessedTables()),
                result.riskLevel(),
                result.success() ? "ALLOW" : "REJECT"
        );
    }

    private void ensureTable() {
        if (tableReady.get()) return;
        synchronized (tableReady) {
            if (tableReady.get()) return;
            jdbcTemplate.execute("""
                    CREATE TABLE IF NOT EXISTS agent_audit_log (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        run_id VARCHAR(64),
                        user_id VARCHAR(64),
                        action VARCHAR(64) NOT NULL,
                        sql_text TEXT,
                        accessed_tables VARCHAR(512),
                        accessed_columns TEXT,
                        risk_level VARCHAR(32),
                        decision VARCHAR(32),
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_run_id (run_id),
                        INDEX idx_user_created (user_id, created_at)
                    )
                    """);
            tableReady.set(true);
        }
    }

    private static String join(java.util.List<String> values) {
        if (values == null || values.isEmpty()) return "";
        StringJoiner joiner = new StringJoiner(",");
        values.forEach(joiner::add);
        return joiner.toString();
    }
}
