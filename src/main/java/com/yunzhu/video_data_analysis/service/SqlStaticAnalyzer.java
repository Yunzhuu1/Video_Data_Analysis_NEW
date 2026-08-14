package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlGateResult;
import com.yunzhu.video_data_analysis.semantic.SensitiveColumns;
import com.yunzhu.video_data_analysis.semantic.TableSchemaRegistry;
import com.yunzhu.video_data_analysis.semantic.TableType;
import net.sf.jsqlparser.expression.Expression;
import net.sf.jsqlparser.expression.ExpressionVisitorAdapter;
import net.sf.jsqlparser.expression.Function;
import net.sf.jsqlparser.parser.CCJSqlParserUtil;
import net.sf.jsqlparser.schema.Column;
import net.sf.jsqlparser.schema.Table;
import net.sf.jsqlparser.statement.Statement;
import net.sf.jsqlparser.statement.select.AllColumns;
import net.sf.jsqlparser.statement.select.AllTableColumns;
import net.sf.jsqlparser.statement.select.FromItem;
import net.sf.jsqlparser.statement.select.GroupByElement;
import net.sf.jsqlparser.statement.select.Join;
import net.sf.jsqlparser.statement.select.ParenthesedSelect;
import net.sf.jsqlparser.statement.select.PlainSelect;
import net.sf.jsqlparser.statement.select.Select;
import net.sf.jsqlparser.statement.select.SelectItem;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * SQL 门禁静态层：基于 jsqlparser AST 做确定性结构检查，不依赖业务库。
 *
 * <p>规则（按序短路）：
 * <ol>
 *   <li>语法（jsqlparser 解析）</li>
 *   <li>SELECT-only</li>
 *   <li>表存在性（TableSchemaRegistry）</li>
 *   <li>明细表 LIMIT / 时间范围（FACT 表）</li>
 *   <li>敏感列（含 SELECT * / 表通配）</li>
 *   <li>字段存在性（别名解析；子查询/CTE 跳过；裸列单表解析；无法解析降级警告）</li>
 *   <li>逻辑规则（event_type 过滤 / JOIN 带 ON / GROUP BY 在 SELECT / content 关联 creator）</li>
 * </ol>
 * 返回 {@code null} 表示静态层通过。
 */
@Component
public class SqlStaticAnalyzer {

    private static final Set<String> TIME_COLUMNS = Set.of("date", "created_at", "event_time", "timestamp", "publish_time");
    private static final Set<String> AGGREGATE_FUNCTIONS = Set.of("SUM", "COUNT", "AVG", "MIN", "MAX");

    private final TableSchemaRegistry registry;

    public SqlStaticAnalyzer(TableSchemaRegistry registry) {
        this.registry = registry;
    }

    private static final Set<String> AGGREGATE_INTENTS = Set.of("aggregate", "trend", "ranking");

    public SqlGateResult analyze(String sql, List<String> accessedTables,
                                 String intent, String intentTimeRangeType) {
        if (sql == null || sql.isBlank()) {
            return SqlGateResult.retryable("SQL_EMPTY", "SQL must not be empty.",
                    "Regenerate a SELECT query from the current schema context.", "HIGH", accessedTables);
        }

        Statement statement;
        try {
            statement = CCJSqlParserUtil.parse(sql);
        } catch (Exception e) {
            return SqlGateResult.retryable("SQL_PARSE_ERROR", "SQL syntax error: " + e.getMessage(),
                    "Fix SQL syntax and only use fields from the provided schema.", "HIGH", accessedTables);
        }

        if (!(statement instanceof Select select)) {
            return SqlGateResult.retryable("SQL_NOT_SELECT", "Only SELECT statements are allowed.",
                    "Rewrite the query as a read-only SELECT statement.", "HIGH", accessedTables);
        }

        // 表存在性
        for (String table : accessedTables) {
            if (!registry.hasTable(table)) {
                return SqlGateResult.retryable("SQL_UNKNOWN_TABLE",
                        "Table '" + table + "' does not exist in the semantic model.",
                        "Rewrite using only tables from the provided schema.", "HIGH", accessedTables);
            }
        }

        PlainSelect plainSelect = select.getPlainSelect();
        if (plainSelect == null) {
            // 集合运算（UNION 等）：只做表存在性，跳过结构细则
            return null;
        }

        // 意图层风险：intent=detail 且意图无时间范围 → 无条件审批（与 SQL 形态无关）
        boolean intentDetailNoTimeRange = "detail".equalsIgnoreCase(intent)
                && (intentTimeRangeType == null || "none".equalsIgnoreCase(intentTimeRangeType));
        if (intentDetailNoTimeRange) {
            return SqlGateResult.approvalNeeded("DETAIL_QUERY_WITHOUT_TIME_RANGE",
                    "Detail intent without a time range in the resolved intent.",
                    "Add a time range to the request, or approve this detail query via HITL.",
                    accessedTables);
        }

        // 明细表规则（聚合意图豁免 LIMIT）
        SqlGateResult detail = checkDetailTables(plainSelect, accessedTables, intent);
        if (detail != null) {
            return detail;
        }

        // 意图-形态一致性：聚合意图但 SQL 为明细形态且触碰 FACT → RETRYABLE
        SqlGateResult shape = checkIntentShape(plainSelect, intent, accessedTables);
        if (shape != null) {
            return shape;
        }

        Map<String, String> aliasToTable = buildAliasMap(plainSelect);

        // 敏感列（SELECT * / 表通配 / 显式列；别名需解析）
        SqlGateResult sensitive = checkSensitiveColumns(plainSelect, accessedTables, aliasToTable);
        if (sensitive != null) {
            return sensitive;
        }

        // 字段存在性 + 逻辑规则
        return checkColumnsAndRules(plainSelect, accessedTables, aliasToTable);
    }

    // ------------------------------------------------------------------
    // 明细表规则
    // ------------------------------------------------------------------

    private SqlGateResult checkDetailTables(PlainSelect select, List<String> accessedTables, String intent) {
        boolean touchesFact = accessedTables.stream()
                .map(TableType::classify)
                .anyMatch(TableType.FACT::equals);
        if (!touchesFact) {
            return null;
        }
        boolean sqlAggregate = !collectFunctionNames(select).isEmpty() || select.getGroupBy() != null;
        boolean aggregateIntent = intent != null && AGGREGATE_INTENTS.contains(intent.toLowerCase(Locale.ROOT));
        // 聚合意图或 SQL 本身聚合 → 豁免 LIMIT（聚合不返回明细行）；时间范围规则仍生效
        boolean isAggregate = aggregateIntent || sqlAggregate;
        if (!isAggregate) {
            boolean hasLimit = select.getLimit() != null && select.getLimit().getRowCount() != null;
            if (!hasLimit) {
                return SqlGateResult.approvalNeeded("DETAIL_QUERY_WITHOUT_LIMIT",
                        "Detail table queries must include LIMIT.",
                        "Add LIMIT or rewrite the query as an aggregate query.", accessedTables);
            }
        }
        Set<String> whereColumns = collectColumnNames(select.getWhere());
        boolean hasTimeFilter = whereColumns.stream().anyMatch(TIME_COLUMNS::contains);
        if (!hasTimeFilter) {
            return SqlGateResult.approvalNeeded("DETAIL_QUERY_WITHOUT_TIME_RANGE",
                    "Detail table queries must include a time range filter.",
                    "Add a date/created_at/timestamp filter to reduce scan scope.", accessedTables);
        }
        return null;
    }

    /** 意图-形态一致性：语义说聚合、SQL 却是明细形态且触碰 FACT → RETRYABLE（LLM 写错，重写）。 */
    private SqlGateResult checkIntentShape(PlainSelect select, String intent, List<String> accessedTables) {
        if (intent == null || !AGGREGATE_INTENTS.contains(intent.toLowerCase(Locale.ROOT))) {
            return null;
        }
        boolean sqlAggregate = !collectFunctionNames(select).isEmpty() || select.getGroupBy() != null;
        if (sqlAggregate) {
            return null;
        }
        boolean touchesFact = accessedTables.stream()
                .map(TableType::classify)
                .anyMatch(TableType.FACT::equals);
        if (!touchesFact) {
            return null;
        }
        return SqlGateResult.retryable("SQL_RULE_WARNING",
                "Aggregate intent but SQL is a detail-shaped query on a fact table.",
                "Rewrite as an aggregate query (GROUP BY / aggregate function) matching the resolved intent.",
                "MEDIUM", accessedTables);
    }

    // ------------------------------------------------------------------
    // 敏感列
    // ------------------------------------------------------------------

    private SqlGateResult checkSensitiveColumns(PlainSelect select, List<String> accessedTables,
                                                Map<String, String> aliasToTable) {
        for (SelectItem<?> item : select.getSelectItems()) {
            Expression expr = item.getExpression();
            if (expr instanceof AllTableColumns allTableColumns) {
                // t.* —— 只检查该表（别名需解析到真实表名）
                Table tableRef = allTableColumns.getTable();
                String table = tableRef != null
                        ? aliasToTable.get(tableRef.getName().toLowerCase(Locale.ROOT))
                        : null;
                if (table != null && registry.columnsOf(table).stream().anyMatch(SensitiveColumns::isSensitive)) {
                    return SqlGateResult.approvalNeeded("SENSITIVE_FIELD_ACCESS",
                            "SELECT " + allTableColumns.getTable().getName() + ".* exposes sensitive columns.",
                            "Select only non-sensitive columns explicitly.", accessedTables);
                }
            } else if (expr instanceof AllColumns) {
                // SELECT * —— 保守：任一访问表含敏感列即审批
                for (String table : accessedTables) {
                    if (registry.columnsOf(table).stream().anyMatch(SensitiveColumns::isSensitive)) {
                        return SqlGateResult.approvalNeeded("SENSITIVE_FIELD_ACCESS",
                                "SELECT * exposes sensitive columns (e.g. user_id) on table '" + table + "'.",
                                "Select only non-sensitive columns explicitly.", accessedTables);
                    }
                }
            } else {
                List<Column> columns = new ArrayList<>();
                collectColumns(expr, columns);
                for (Column col : columns) {
                    if (SensitiveColumns.isSensitive(col.getColumnName())) {
                        return SqlGateResult.approvalNeeded("SENSITIVE_FIELD_ACCESS",
                                "Query accesses sensitive column '" + col.getColumnName() + "'.",
                                "Remove sensitive columns from the SELECT list.", accessedTables);
                    }
                }
            }
        }
        return null;
    }

    // ------------------------------------------------------------------
    // 字段存在性 + 逻辑规则
    // ------------------------------------------------------------------

    private SqlGateResult checkColumnsAndRules(PlainSelect select, List<String> accessedTables,
                                               Map<String, String> aliasToTable) {
        // F2: 唯一真实表数 == 1 时裸列可解析（别名也计入 key，须按值去重）
        Set<String> uniqueTables = new HashSet<>(aliasToTable.values());
        String singleTable = uniqueTables.size() == 1 ? uniqueTables.iterator().next() : null;

        List<Column> columns = new ArrayList<>();
        collectSelectColumns(select, columns);

        // 字段存在性
        for (Column column : columns) {
            if (column.getColumnName() == null || "*".equals(column.getColumnName())) {
                continue;
            }
            String tableName = resolveTable(column, aliasToTable, singleTable);
            if (tableName == null) {
                continue; // 子查询/CTE/多表裸列等无法判定 → 跳过（不误伤）
            }
            if (!registry.hasColumn(tableName, column.getColumnName())) {
                return SqlGateResult.retryable("SQL_UNKNOWN_COLUMN",
                        "Column '" + column.getColumnName() + "' does not exist on table '" + tableName + "'.",
                        "Use only columns defined in the provided schema.", "HIGH", accessedTables);
            }
        }

        return checkLogicalRules(select, columns, accessedTables);
    }

    private SqlGateResult checkLogicalRules(PlainSelect select, List<Column> columns, List<String> accessedTables) {
        Set<String> columnNames = new HashSet<>();
        for (Column c : columns) {
            if (c.getColumnName() != null) {
                columnNames.add(c.getColumnName().toLowerCase(Locale.ROOT));
            }
        }
        // 仅 SELECT 列表的列（GROUP BY 规则用；不含 WHERE/GROUP BY 自身）
        Set<String> selectColumnNames = new HashSet<>();
        for (SelectItem<?> item : select.getSelectItems()) {
            List<Column> selectCols = new ArrayList<>();
            collectColumns(item.getExpression(), selectCols);
            for (Column c : selectCols) {
                if (c.getColumnName() != null) {
                    selectColumnNames.add(c.getColumnName().toLowerCase(Locale.ROOT));
                }
            }
        }
        boolean hasAggregation = !collectFunctionNames(select).isEmpty() || select.getGroupBy() != null;
        boolean hasEventTypeFilter = columnNames.contains("event_type");

        // 聚合查询在 FACT 表上应带 event_type 过滤（MEDIUM，可重试修复）
        boolean touchesFact = accessedTables.stream()
                .map(TableType::classify)
                .anyMatch(TableType.FACT::equals);
        if (touchesFact && hasAggregation && !hasEventTypeFilter) {
            return SqlGateResult.retryable("SQL_RULE_WARNING",
                    "Aggregate query on fact table may miss an event_type filter.",
                    "Add an event_type filter (e.g. event_type = 'play') to avoid double counting.",
                    "MEDIUM", accessedTables);
        }

        // JOIN 必须带 ON
        if (select.getJoins() != null) {
            for (Join join : select.getJoins()) {
                if (join.getOnExpressions() == null || join.getOnExpressions().isEmpty()) {
                    return SqlGateResult.retryable("SQL_RULE_WARNING",
                            "JOIN without ON condition is not allowed.",
                            "Add an explicit ON condition for the JOIN.", "MEDIUM", accessedTables);
                }
            }
        }

        // GROUP BY 字段必须在 SELECT 中
        GroupByElement groupBy = select.getGroupBy();
        if (groupBy != null && groupBy.getGroupByExpressionList() != null) {
            for (Object exprObj : groupBy.getGroupByExpressionList().getExpressions()) {
                if (exprObj instanceof Expression expr && expr instanceof Column groupCol
                        && groupCol.getColumnName() != null) {
                    String name = groupCol.getColumnName();
                    if (!selectColumnNames.contains(name.toLowerCase(Locale.ROOT)) && !containsSelectAlias(select, name)) {
                        return SqlGateResult.retryable("SQL_RULE_WARNING",
                                "GROUP BY column '" + name + "' must appear in the SELECT list.",
                                "Add the column to SELECT or remove it from GROUP BY.", "MEDIUM", accessedTables);
                    }
                }
            }
        }
        return null;
    }

    private boolean containsSelectAlias(PlainSelect select, String column) {
        for (SelectItem<?> item : select.getSelectItems()) {
            if (item.getAlias() != null && column.equalsIgnoreCase(item.getAlias().getName())) {
                return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------------
    // AST 辅助
    // ------------------------------------------------------------------

    private Map<String, String> buildAliasMap(PlainSelect select) {
        Map<String, String> map = new HashMap<>();
        FromItem from = select.getFromItem();
        if (from instanceof Table table) {
            addAlias(map, table);
        }
        if (select.getJoins() != null) {
            for (Join join : select.getJoins()) {
                if (join.getRightItem() instanceof Table table) {
                    addAlias(map, table);
                }
            }
        }
        return map;
    }

    private void addAlias(Map<String, String> map, Table table) {
        if (table.getName() == null) {
            return;
        }
        String lower = table.getName().toLowerCase(Locale.ROOT);
        map.put(lower, lower);
        if (table.getAlias() != null && table.getAlias().getName() != null) {
            map.put(table.getAlias().getName().toLowerCase(Locale.ROOT), lower);
        }
    }

    private String resolveTable(Column column, Map<String, String> aliasToTable, String singleTable) {
        Table table = column.getTable();
        if (table == null || table.getName() == null) {
            return singleTable;
        }
        return aliasToTable.get(table.getName().toLowerCase(Locale.ROOT));
    }

    private void collectSelectColumns(PlainSelect select, List<Column> out) {
        for (SelectItem<?> item : select.getSelectItems()) {
            collectColumns(item.getExpression(), out);
        }
        collectColumns(select.getWhere(), out);
        if (select.getGroupBy() != null && select.getGroupBy().getGroupByExpressionList() != null) {
            for (Object exprObj : select.getGroupBy().getGroupByExpressionList().getExpressions()) {
                if (exprObj instanceof Expression expr) {
                    collectColumns(expr, out);
                }
            }
        }
        collectColumns(select.getHaving(), out);
        if (select.getOrderByElements() != null) {
            for (var order : select.getOrderByElements()) {
                collectColumns(order.getExpression(), out);
            }
        }
    }

    private Set<String> collectFunctionNames(PlainSelect select) {
        Set<String> out = new HashSet<>();
        for (SelectItem<?> item : select.getSelectItems()) {
            collectFunctionNames(item.getExpression(), out);
        }
        return out;
    }

    private void collectFunctionNames(Expression expr, Set<String> out) {
        if (expr == null) {
            return;
        }
        expr.accept(new ExpressionVisitorAdapter() {
            @Override
            public void visit(Function function) {
                if (function.getName() != null) {
                    out.add(function.getName().toUpperCase(Locale.ROOT));
                }
                if (function.getParameters() != null && function.getParameters().getExpressions() != null) {
                    for (Expression e : function.getParameters().getExpressions()) {
                        e.accept(this);
                    }
                }
            }

            @Override
            public void visit(ParenthesedSelect parenthesedSelect) {
                // 不下钻子查询
            }
        });
    }

    private Set<String> collectColumnNames(Expression expr) {
        List<Column> list = new ArrayList<>();
        collectColumns(expr, list);
        Set<String> names = new HashSet<>();
        for (Column c : list) {
            if (c.getColumnName() != null) {
                names.add(c.getColumnName().toLowerCase(Locale.ROOT));
            }
        }
        return names;
    }

    private void collectColumns(Expression expr, List<Column> out) {
        if (expr == null) {
            return;
        }
        expr.accept(new ExpressionVisitorAdapter() {
            @Override
            public void visit(Column column) {
                out.add(column);
            }

            @Override
            public void visit(ParenthesedSelect parenthesedSelect) {
                // 不下钻子查询
            }
        });
    }
}
