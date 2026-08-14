package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlExecuteRequest;
import com.yunzhu.video_data_analysis.dto.SqlExecuteResult;
import org.springframework.jdbc.core.ColumnMapRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * SQL 执行网关：只负责执行与熔断，不再承担任何门禁检查。
 *
 * <p>审批放行不变式（D8）：SQL 质量门禁仅在编排层 {@code SQL_HARD_GUARD} 经
 * {@code /internal/sql/validate} 调用一次；执行层永不重跑门禁，避免把已审批的 SQL
 * 二次拦截（审批对象漂移）。这里只做：熔断检查 → 执行 → 审计。
 */
@Service
public class SqlExecutionService {

    private static final int MAX_ROWS = 100;
    private static final int QUERY_TIMEOUT_SECONDS = 15;
    private static final int CIRCUIT_BREAKER_THRESHOLD = 3;

    private final JdbcTemplate jdbcTemplate;
    private final SqlAuditService sqlAuditService;
    private final AtomicInteger consecutiveFailures = new AtomicInteger(0);

    private final ThreadLocal<String> lastExecutedSql = ThreadLocal.withInitial(() -> "");

    public SqlExecutionService(JdbcTemplate jdbcTemplate, SqlAuditService sqlAuditService) {
        this.jdbcTemplate = jdbcTemplate;
        this.sqlAuditService = sqlAuditService;
    }

    public String getLastExecutedSql() {
        return lastExecutedSql.get();
    }

    public SqlExecuteResult execute(SqlExecuteRequest request) {
        long start = System.currentTimeMillis();
        String sql = request.sql();
        List<String> accessedTables = SqlGateService.extractAccessedTables(sql);

        if (consecutiveFailures.get() >= CIRCUIT_BREAKER_THRESHOLD) {
            consecutiveFailures.set(0);
            return auditAndReturn(request, rejected(sql, "SQL_CIRCUIT_BREAKER",
                    "Previous SQL queries timed out repeatedly. Please simplify the query, add WHERE filters, "
                            + "and avoid table scans.",
                    "HIGH", accessedTables, start));
        }

        lastExecutedSql.set(sql);
        try {
            List<Map<String, Object>> results = jdbcTemplate.query(
                    connection -> {
                        var ps = connection.prepareStatement(sql);
                        ps.setMaxRows(MAX_ROWS + 1);
                        ps.setQueryTimeout(QUERY_TIMEOUT_SECONDS);
                        return ps;
                    },
                    new ColumnMapRowMapper()
            );
            consecutiveFailures.set(0);

            boolean truncated = results.size() > MAX_ROWS;
            if (truncated) {
                results = new ArrayList<>(results.subList(0, MAX_ROWS));
            }

            List<String> columns = results.isEmpty()
                    ? List.of()
                    : new ArrayList<>(results.get(0).keySet());
            int rowCount = results.size();
            SqlExecuteResult result = new SqlExecuteResult(true, sql, null, columns, results, rowCount, truncated,
                    List.of(), null, null, "LOW", accessedTables, elapsed(start));
            return auditAndReturn(request, result);
        } catch (Exception e) {
            String msg = e.getMessage();
            if (msg != null && msg.contains("timeout")) {
                consecutiveFailures.incrementAndGet();
            }
            return auditAndReturn(request, rejected(sql, "SQL_EXECUTION_ERROR",
                    "SQL Execution Error: " + msg, "LOW", accessedTables, start));
        }
    }

    private SqlExecuteResult rejected(String sql, String errorCode, String message,
                                      String riskLevel, List<String> accessedTables, long start) {
        return new SqlExecuteResult(false, sql, message, List.of(), List.of(), 0, false,
                List.of(), errorCode, message, riskLevel, accessedTables, elapsed(start));
    }

    private SqlExecuteResult auditAndReturn(SqlExecuteRequest request, SqlExecuteResult result) {
        sqlAuditService.record(request, result);
        return result;
    }

    private static long elapsed(long start) {
        return System.currentTimeMillis() - start;
    }
}
