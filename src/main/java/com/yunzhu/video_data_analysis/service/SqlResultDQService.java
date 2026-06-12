package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlDQCheckRequest;
import com.yunzhu.video_data_analysis.dto.SqlDQCheckResult;
import com.yunzhu.video_data_analysis.dto.SqlExecuteResult;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Rule-based soft DQ guard for SQL result usefulness. */
@Service
public class SqlResultDQService {

    public SqlDQCheckResult check(SqlDQCheckRequest request) {
        SqlExecuteResult result = request.queryResult();
        if (result == null || !result.success()) {
            return fail("HIGH", "SQL result is not successful.",
                    "Regenerate SQL or fix execution errors.");
        }
        if (result.rows() == null || result.rows().isEmpty()) {
            return fail("HIGH", "SQL result is empty.",
                    "Relax filters or verify the requested time range and dimensions.");
        }

        List<String> columns = result.columns() == null ? List.of() : result.columns();
        List<String> warnings = new ArrayList<>();
        String question = request.question() == null ? "" : request.question().toLowerCase(Locale.ROOT);

        if (asksTrend(question) && !hasAny(columns, "date", "time", "created_at", "day", "month")) {
            return fail("HIGH", "Trend question result lacks a time column.",
                    "Regenerate SQL with a date/time field in SELECT.");
        }
        if (asksComparison(question) && !hasAny(columns, "category", "type", "creator", "content", "dimension")) {
            return fail("HIGH", "Comparison question result lacks a dimension column.",
                    "Regenerate SQL with the compared dimension in SELECT.");
        }
        if (asksMetric(question) && !hasMetricColumn(columns)) {
            return fail("HIGH", "Metric question result lacks a metric column.",
                    "Regenerate SQL with an aggregate metric field.");
        }
        if (metricColumnsAllNull(columns, result.rows())) {
            return fail("HIGH", "Metric columns are all null.",
                    "Check metric formula, filters, and source table.");
        }
        String completionRateIssue = completionRateIssue(columns, result.rows());
        if (completionRateIssue != null) {
            return fail("HIGH", completionRateIssue,
                    "Clamp invalid formulas or recompute completion rate from source fields.");
        }
        if (result.truncated()) {
            warnings.add("Result was truncated; answer should mention partial data.");
        }

        String risk = warnings.isEmpty() ? "LOW" : "MEDIUM";
        return new SqlDQCheckResult(true, risk, null, null, warnings);
    }

    private static SqlDQCheckResult fail(String riskLevel, String reason, String suggestion) {
        return new SqlDQCheckResult(false, riskLevel, reason, suggestion, List.of());
    }

    private static boolean asksTrend(String question) {
        return containsAny(question, "trend", "change", "over time", "daily", "weekly", "monthly");
    }

    private static boolean asksComparison(String question) {
        return containsAny(question, "compare", "comparison", "category", "rank", "top", "by ");
    }

    private static boolean asksMetric(String question) {
        return containsAny(question, "plays", "rate", "count", "sum", "avg", "metric", "completion");
    }

    private static boolean hasAny(List<String> columns, String... keywords) {
        return columns.stream()
                .map(column -> column.toLowerCase(Locale.ROOT))
                .anyMatch(column -> containsAny(column, keywords));
    }

    private static boolean hasMetricColumn(List<String> columns) {
        return hasAny(columns, "play", "rate", "count", "sum", "avg", "total", "metric", "duration");
    }

    private static boolean metricColumnsAllNull(List<String> columns, List<Map<String, Object>> rows) {
        List<String> metricColumns = columns.stream()
                .filter(column -> hasMetricColumn(List.of(column)))
                .toList();
        if (metricColumns.isEmpty()) {
            return false;
        }
        return metricColumns.stream()
                .allMatch(column -> rows.stream().allMatch(row -> row.get(column) == null));
    }

    private static String completionRateIssue(List<String> columns, List<Map<String, Object>> rows) {
        List<String> rateColumns = columns.stream()
                .filter(column -> column.toLowerCase(Locale.ROOT).contains("completion_rate"))
                .toList();
        for (String column : rateColumns) {
            for (Map<String, Object> row : rows) {
                Object value = row.get(column);
                if (value == null) {
                    continue;
                }
                BigDecimal decimal = new BigDecimal(value.toString());
                if (decimal.compareTo(BigDecimal.ZERO) < 0 || decimal.compareTo(BigDecimal.valueOf(100)) > 0) {
                    return "Completion rate is outside [0, 100].";
                }
            }
        }
        return null;
    }

    private static boolean containsAny(String text, String... keywords) {
        for (String keyword : keywords) {
            if (text.contains(keyword)) {
                return true;
            }
        }
        return false;
    }
}
