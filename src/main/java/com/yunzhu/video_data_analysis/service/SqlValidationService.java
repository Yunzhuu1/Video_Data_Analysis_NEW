package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlValidateRequest;
import com.yunzhu.video_data_analysis.dto.SqlValidateResult;
import com.yunzhu.video_data_analysis.dto.SqlViolation;
import com.yunzhu.video_data_analysis.util.SqlParserValidator;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;

/** Hard SQL guard used before agent-generated SQL is executed. */
@Service
public class SqlValidationService {

    private static final Pattern SELECT_PATTERN =
            Pattern.compile("^\\s*(--.*\\n)*\\s*SELECT\\b.*", Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
    private static final Pattern LIMIT_PATTERN =
            Pattern.compile("\\bLIMIT\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern TIME_FILTER_PATTERN =
            Pattern.compile("\\b(date|created_at|event_time|timestamp)\\b\\s*(=|>|<|>=|<=|BETWEEN|IN)\\b",
                    Pattern.CASE_INSENSITIVE);
    private static final List<String> DETAIL_TABLES = List.of("play_detail", "user_behavior_fact");

    private final SqlParserValidator sqlParserValidator;

    public SqlValidationService(SqlParserValidator sqlParserValidator) {
        this.sqlParserValidator = sqlParserValidator;
    }

    public SqlValidateResult validate(SqlValidateRequest request) {
        String sql = request.sql();
        List<String> accessedTables = extractAccessedTables(sql);
        List<SqlViolation> violations = new ArrayList<>();

        if (sql == null || sql.isBlank()) {
            violations.add(new SqlViolation("SQL_EMPTY", "HIGH", "SQL must not be empty.",
                    "Regenerate a SELECT query from the current schema context."));
            return reject(sql, "SQL_EMPTY", violations, accessedTables);
        }

        if (!SELECT_PATTERN.matcher(sql).matches()) {
            violations.add(new SqlViolation("SQL_NOT_SELECT", "HIGH", "Only SELECT statements are allowed.",
                    "Rewrite the query as a read-only SELECT statement."));
            return reject(sql, "SQL_NOT_SELECT", violations, accessedTables);
        }

        String parseError = sqlParserValidator.validate(sql);
        if (parseError != null) {
            violations.add(new SqlViolation("SQL_PARSE_ERROR", "HIGH", parseError,
                    "Fix SQL syntax and only use fields from the provided schema."));
            return reject(sql, "SQL_PARSE_ERROR", violations, accessedTables);
        }

        validateDetailTables(sql, accessedTables, violations);

        String riskLevel = highestSeverity(violations);
        boolean hasBlockingViolation = violations.stream()
                .anyMatch(violation -> "HIGH".equalsIgnoreCase(violation.severity()));
        if (hasBlockingViolation && !request.allowHighRisk()) {
            return reject(sql, violations.get(0).code(), violations, accessedTables);
        }

        return SqlValidateResult.pass(sql, riskLevel, accessedTables, violations);
    }

    private void validateDetailTables(String sql, List<String> accessedTables, List<SqlViolation> violations) {
        boolean touchesDetailTable = accessedTables.stream().map(table -> table.toLowerCase(Locale.ROOT))
                .anyMatch(DETAIL_TABLES::contains);
        if (!touchesDetailTable) {
            return;
        }
        if (!LIMIT_PATTERN.matcher(sql).find()) {
            violations.add(new SqlViolation("DETAIL_QUERY_WITHOUT_LIMIT", "HIGH",
                    "Detail table queries must include LIMIT.",
                    "Add LIMIT or rewrite the query as an aggregate query."));
        }
        if (!TIME_FILTER_PATTERN.matcher(sql).find()) {
            violations.add(new SqlViolation("DETAIL_QUERY_WITHOUT_TIME_RANGE", "MEDIUM",
                    "Detail table queries should include a time range.",
                    "Add a date or created_at filter to reduce scan scope."));
        }
    }

    private static SqlValidateResult reject(String sql, String errorCode, List<SqlViolation> violations,
                                            List<String> accessedTables) {
        SqlViolation first = violations.isEmpty()
                ? new SqlViolation(errorCode, "HIGH", "SQL validation failed.", "Regenerate SQL.")
                : violations.get(0);
        return SqlValidateResult.rejected(sql, highestSeverity(violations), errorCode,
                first.message(), first.suggestion(), accessedTables, violations);
    }

    private static String highestSeverity(List<SqlViolation> violations) {
        if (violations.stream().anyMatch(violation -> "HIGH".equalsIgnoreCase(violation.severity()))) {
            return "HIGH";
        }
        if (violations.stream().anyMatch(violation -> "MEDIUM".equalsIgnoreCase(violation.severity()))) {
            return "MEDIUM";
        }
        return "LOW";
    }

    static List<String> extractAccessedTables(String sql) {
        if (sql == null || sql.isBlank()) {
            return List.of();
        }
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
}
