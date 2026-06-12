package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlExecuteRequest;
import com.yunzhu.video_data_analysis.dto.SqlExecuteResult;
import com.yunzhu.video_data_analysis.dto.SqlValidateRequest;
import com.yunzhu.video_data_analysis.dto.SqlValidateResult;
import com.yunzhu.video_data_analysis.tool.SqlRulesChecker;
import com.yunzhu.video_data_analysis.util.SqlParserValidator;
import org.springframework.jdbc.core.ColumnMapRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Pattern;

/** Platform SQL execution gateway used by Agent tools and future LangGraph calls. */
@Service
public class SqlExecutionService {

    private static final int MAX_ROWS = 100;
    private static final int QUERY_TIMEOUT_SECONDS = 15;
    private static final int CIRCUIT_BREAKER_THRESHOLD = 3;

    private static final Pattern SELECT_PATTERN =
            Pattern.compile("^\\s*(--.*\\n)*\\s*SELECT\\b.*", Pattern.CASE_INSENSITIVE | Pattern.DOTALL);

    private final JdbcTemplate jdbcTemplate;
    private final SqlResultCache sqlResultCache;
    private final SqlRulesChecker sqlRulesChecker;
    private final SqlParserValidator sqlParserValidator;
    private final SqlValidationService sqlValidationService;
    private final SlowQueryService slowQueryService;
    private final SqlAuditService sqlAuditService;
    private final AtomicInteger consecutiveFailures = new AtomicInteger(0);

    private final ThreadLocal<String> lastExecutedSql = ThreadLocal.withInitial(() -> "");

    public SqlExecutionService(JdbcTemplate jdbcTemplate,
                               SqlResultCache sqlResultCache,
                               SqlRulesChecker sqlRulesChecker,
                               SqlParserValidator sqlParserValidator,
                               SqlValidationService sqlValidationService,
                               SlowQueryService slowQueryService,
                               SqlAuditService sqlAuditService) {
        this.jdbcTemplate = jdbcTemplate;
        this.sqlResultCache = sqlResultCache;
        this.sqlRulesChecker = sqlRulesChecker;
        this.sqlParserValidator = sqlParserValidator;
        this.sqlValidationService = sqlValidationService;
        this.slowQueryService = slowQueryService;
        this.sqlAuditService = sqlAuditService;
    }

    public String getLastExecutedSql() {
        return lastExecutedSql.get();
    }

    public SqlExecuteResult execute(SqlExecuteRequest request) {
        long start = System.currentTimeMillis();
        String sql = request.sql();
        List<String> accessedTables = extractAccessedTables(sql);

        SqlValidateResult validation = sqlValidationService.validate(new SqlValidateRequest(
                request.runId(),
                request.userId(),
                request.question(),
                sql,
                request.purpose(),
                request.allowHighRisk()
        ));
        if (!validation.pass()) {
            return auditAndReturn(request, rejected(sql, validation.errorCode(),
                    validation.reason() + " Suggestion: " + validation.suggestion(),
                    validation.riskLevel(), validation.accessedTables(), start));
        }
        accessedTables = validation.accessedTables();

        if (!SELECT_PATTERN.matcher(sql).matches()) {
            return auditAndReturn(request, rejected(sql, "SQL_NOT_SELECT",
                    "Error: Only SELECT statements are allowed. Your statement was rejected: " + sql,
                    "HIGH", accessedTables, start));
        }
        String parseError = sqlParserValidator.validate(sql);
        if (parseError != null) {
            return auditAndReturn(request, rejected(sql, "SQL_SYNTAX_ERROR",
                    "SQL Syntax Error: " + parseError, "LOW", accessedTables, start));
        }

        lastExecutedSql.set(sql);

        String cached = sqlResultCache.get(sql);
        if (cached != null) {
            return auditAndReturn(request, new SqlExecuteResult(true, sql, cached, List.of(), List.of(), 0, false,
                    List.of(), null, null, "LOW", accessedTables, elapsed(start)));
        }

        String ruleWarning = sqlRulesChecker.check(sql);
        if (ruleWarning != null) {
            return auditAndReturn(request, rejected(sql, "SQL_RULE_WARNING", ruleWarning,
                    "MEDIUM", accessedTables, start));
        }

        SqlExecuteResult planWarning = analyzePlan(sql, accessedTables, start);
        if (planWarning != null) {
            return auditAndReturn(request, planWarning);
        }

        if (consecutiveFailures.get() >= CIRCUIT_BREAKER_THRESHOLD) {
            consecutiveFailures.set(0);
            return auditAndReturn(request, rejected(sql, "SQL_CIRCUIT_BREAKER",
                    "Warning: Previous SQL queries timed out repeatedly. "
                    + "Please simplify the query, add proper WHERE filters, "
                    + "and avoid table scans. Retry your simplified SQL.", "HIGH", accessedTables, start));
        }

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
            sqlResultCache.put(sql, result.toToolResponse());
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

    private SqlExecuteResult analyzePlan(String sql, List<String> accessedTables, long start) {
        try {
            List<Map<String, Object>> plan = jdbcTemplate.queryForList("EXPLAIN " + sql);
            for (Map<String, Object> row : plan) {
                String type = (String) row.get("type");
                String extra = (String) row.get("Extra");
                Number rows = (Number) row.get("rows");

                if ("ALL".equals(type)) {
                    String table = (String) row.get("table");
                    long r = rows != null ? rows.longValue() : 0;
                    slowQueryService.record("FULL_SCAN", sql, table, r);
                    return rejected(sql, "SQL_FULL_SCAN", "SQL Performance Warning: Full table scan on '" + table
                            + "' (" + r + " rows). Add WHERE conditions on indexed columns.",
                            "HIGH", accessedTables, start);
                }
                if (extra != null && extra.contains("Using temporary")) {
                    slowQueryService.record("TEMP_TABLE", sql, (String) row.get("table"),
                            rows != null ? rows.longValue() : 0);
                    return rejected(sql, "SQL_TEMP_TABLE", "SQL Performance Warning: Query uses temporary table. "
                            + "Consider indexing GROUP BY/ORDER BY columns or simplifying the query.",
                            "MEDIUM", accessedTables, start);
                }
                if (extra != null && extra.contains("Using filesort")) {
                    slowQueryService.record("FILESORT", sql, (String) row.get("table"),
                            rows != null ? rows.longValue() : 0);
                    return rejected(sql, "SQL_FILESORT", "SQL Performance Warning: Query uses filesort. "
                            + "Consider adding indexes for ORDER BY columns.", "MEDIUM", accessedTables, start);
                }
                if (rows != null && rows.longValue() > 100000) {
                    slowQueryService.record("LARGE_SCAN", sql, (String) row.get("table"), rows.longValue());
                    return rejected(sql, "SQL_LARGE_SCAN", "SQL Performance Warning: Scanning " + rows + " rows. "
                            + "Add more specific WHERE filters to reduce the scan range.",
                            "HIGH", accessedTables, start);
                }
            }
            return null;
        } catch (Exception e) {
            return rejected(sql, "SQL_COMPILE_ERROR", "SQL Compile Error: " + e.getMessage() + ". SQL: " + sql,
                    "LOW", accessedTables, start);
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

    private static List<String> extractAccessedTables(String sql) {
        if (sql == null || sql.isBlank()) return List.of();
        Set<String> tables = new LinkedHashSet<>();
        java.util.regex.Matcher matcher = Pattern
                .compile("\\b(?:FROM|JOIN)\\s+([`\\w.]+)", Pattern.CASE_INSENSITIVE)
                .matcher(sql);
        while (matcher.find()) {
            String table = matcher.group(1).replace("`", "");
            int dot = table.lastIndexOf('.');
            tables.add(dot >= 0 ? table.substring(dot + 1) : table);
        }
        return List.copyOf(tables);
    }

    private static long elapsed(long start) {
        return System.currentTimeMillis() - start;
    }
}
