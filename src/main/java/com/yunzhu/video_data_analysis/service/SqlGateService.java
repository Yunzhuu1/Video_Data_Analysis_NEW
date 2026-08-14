package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlGateResult;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 统一 SQL 门禁（单一权威）：静态语义层（SqlStaticAnalyzer）→ 计划层（PlanAnalyzer），
 * 返回 {@code PASS / RETRYABLE / APPROVAL_NEEDED} 三态。
 *
 * <p>审批放行不变式（D8）：门禁仅在编排层 {@code SQL_HARD_GUARD} 以 {@code allowHighRisk=false}
 * 调用一次；执行层永不重跑门禁。{@code allowHighRisk=true} 仅作为防御性语义：若被调用，
 * APPROVAL_NEEDED 视为已审批放行，RETRYABLE 仍拦截。
 */
@Service
public class SqlGateService {

    private static final Pattern FROM_JOIN_PATTERN = Pattern.compile("\\b(?:FROM|JOIN)\\s+([`\\w.]+)", Pattern.CASE_INSENSITIVE);

    private final SqlStaticAnalyzer staticAnalyzer;
    private final PlanAnalyzer planAnalyzer;

    public SqlGateService(SqlStaticAnalyzer staticAnalyzer, PlanAnalyzer planAnalyzer) {
        this.staticAnalyzer = staticAnalyzer;
        this.planAnalyzer = planAnalyzer;
    }

    public SqlGateResult evaluate(String sql, boolean allowHighRisk) {
        List<String> accessedTables = extractAccessedTables(sql);
        SqlGateResult staticResult = staticAnalyzer.analyze(sql, accessedTables);
        if (staticResult != null) {
            return allowHighRisk && "APPROVAL_NEEDED".equals(staticResult.verdict())
                    ? SqlGateResult.pass(sql, accessedTables)
                    : staticResult;
        }
        SqlGateResult planResult = planAnalyzer.analyzePlan(sql, accessedTables);
        if (planResult != null) {
            return allowHighRisk && "APPROVAL_NEEDED".equals(planResult.verdict())
                    ? SqlGateResult.pass(sql, accessedTables)
                    : planResult;
        }
        return SqlGateResult.pass(sql, accessedTables);
    }

    /** 提取 SQL 访问的表（FROM/JOIN 正则，与旧实现一致）。 */
    public static List<String> extractAccessedTables(String sql) {
        if (sql == null || sql.isBlank()) {
            return List.of();
        }
        Set<String> tables = new LinkedHashSet<>();
        Matcher matcher = FROM_JOIN_PATTERN.matcher(sql);
        while (matcher.find()) {
            String table = matcher.group(1).replace("`", "");
            int dot = table.lastIndexOf('.');
            tables.add(dot >= 0 ? table.substring(dot + 1) : table);
        }
        return new ArrayList<>(tables);
    }
}
