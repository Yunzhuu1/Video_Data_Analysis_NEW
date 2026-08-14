package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yunzhu.video_data_analysis.dto.SqlGateResult;
import com.yunzhu.video_data_analysis.semantic.TableType;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * 门禁计划层：基于 {@code EXPLAIN FORMAT=JSON} 判定执行风险。
 *
 * <p>JSON 计划中的 {@code table_name} 是真实表名（不受别名影响），据此做表类型感知：
 * <ul>
 *   <li>{@code access_type=ALL}（全表扫描）：FACT 表 → APPROVAL_NEEDED；AGGREGATE/DIM → 放行</li>
 *   <li>{@code using_temporary_table} / {@code using_filesort} → RETRYABLE（带优化建议）</li>
 *   <li>扫描行数超阈值且 FACT 表 → APPROVAL_NEEDED（SQL_LARGE_SCAN）</li>
 * </ul>
 * EXPLAIN 只生成执行计划、不执行查询，放在门禁是安全的。
 */
@Component
public class JdbcPlanAnalyzer implements PlanAnalyzer {

    private static final Logger log = LoggerFactory.getLogger(JdbcPlanAnalyzer.class);

    private static final long LARGE_ROW_THRESHOLD = 100_000L;

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;
    private final SlowQueryService slowQueryService;

    public JdbcPlanAnalyzer(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper,
                            SlowQueryService slowQueryService) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
        this.slowQueryService = slowQueryService;
    }

    @Override
    public SqlGateResult analyzePlan(String sql, List<String> accessedTables) {
        String json;
        try {
            json = jdbcTemplate.queryForObject("EXPLAIN FORMAT=JSON " + sql, String.class);
        } catch (Exception e) {
            // EXPLAIN 失败（运行时错误）→ 计划层放行，交给执行层报错
            log.warn("EXPLAIN failed for sql: {} -> {}", sql, e.getMessage());
            return null;
        }
        try {
            PlanInfo info = collect(objectMapper.readTree(json));
            for (PlanTable t : info.tables()) {
                if ("ALL".equalsIgnoreCase(t.accessType())) {
                    if (TableType.classify(t.tableName()) == TableType.FACT) {
                        slowQueryService.record("FULL_SCAN", sql, t.tableName(), t.rows());
                        return SqlGateResult.approvalNeeded("SQL_FULL_SCAN",
                                "Full table scan on fact table '" + t.tableName() + "' (" + t.rows() + " rows).",
                                "Add WHERE conditions on indexed columns, or approve this high-risk query via HITL.",
                                accessedTables);
                    }
                    // AGGREGATE/DIM/未知表全扫：预聚合表/维度表行数有界，放行
                }
                if (t.rows() > LARGE_ROW_THRESHOLD && TableType.classify(t.tableName()) == TableType.FACT) {
                    slowQueryService.record("LARGE_SCAN", sql, t.tableName(), t.rows());
                    return SqlGateResult.approvalNeeded("SQL_LARGE_SCAN",
                            "Large scan on fact table '" + t.tableName() + "' (" + t.rows() + " rows).",
                            "Add more specific WHERE filters to reduce the scan range, or approve via HITL.",
                            accessedTables);
                }
            }
            boolean touchesFact = info.tables().stream()
                    .map(t -> TableType.classify(t.tableName()))
                    .anyMatch(TableType.FACT::equals);
            if (info.temporary() && touchesFact) {
                return SqlGateResult.retryable("SQL_TEMP_TABLE",
                        "Query uses a temporary table (GROUP BY/ORDER BY on non-indexed columns) on a fact table.",
                        "Simplify the query or add indexes for GROUP BY/ORDER BY columns.", "MEDIUM", accessedTables);
            }
            if (info.filesort() && touchesFact) {
                return SqlGateResult.retryable("SQL_FILESORT",
                        "Query uses filesort (ORDER BY on non-indexed column) on a fact table.",
                        "Add an index for the ORDER BY column.", "MEDIUM", accessedTables);
            }
            // 仅聚合/维度表的临时表/排序：代价可忽略（表类型感知），放行
            return null;
        } catch (Exception e) {
            log.warn("Failed to parse EXPLAIN JSON: {}", e.getMessage());
            return null;
        }
    }

    private PlanInfo collect(JsonNode root) {
        PlanInfo info = new PlanInfo();
        walk(root, info);
        return info;
    }

    private void walk(JsonNode node, PlanInfo info) {
        if (node == null) {
            return;
        }
        if (node.has("table_name")) {
            info.tables().add(new PlanTable(
                    node.path("table_name").asText(),
                    node.path("access_type").asText(),
                    node.path("rows_examined_per_scan").asLong(0)));
        }
        if (node.path("using_temporary_table").asBoolean(false)) {
            info.temporary = true;
        }
        if (node.path("using_filesort").asBoolean(false)) {
            info.filesort = true;
        }
        node.forEach(child -> walk(child, info));
    }

    record PlanTable(String tableName, String accessType, long rows) {
    }

    static final class PlanInfo {
        private final List<PlanTable> tables = new ArrayList<>();
        private boolean temporary;
        private boolean filesort;

        List<PlanTable> tables() {
            return tables;
        }

        boolean temporary() {
            return temporary;
        }

        boolean filesort() {
            return filesort;
        }
    }
}
