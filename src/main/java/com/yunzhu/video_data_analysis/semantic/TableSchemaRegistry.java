package com.yunzhu.video_data_analysis.semantic;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * 表-列注册表：从 {@code src/main/resources/schema.sql} 解析建表语句，
 * 得到 {@code 表名 → 列集合}，作为语义层模型的静态部分。
 *
 * <p>schema.sql 是 DDL 的唯一源（AGENTS.md 约束），解析它 = 零业务库依赖、
 * 与 DDL 同源、mock/真实 schema 天然一致。支持 {@code CREATE TABLE IF NOT EXISTS}、
 * 内联 {@code UNIQUE}、{@code COMMENT} 含逗号/单引号转义（{@code ''}）、
 * 表内 {@code INDEX/PRIMARY KEY} 约束行（不计为列）。
 */
@Component
public class TableSchemaRegistry {

    private static final Logger log = LoggerFactory.getLogger(TableSchemaRegistry.class);

    private static final Set<String> NON_COLUMN_KEYWORDS = Set.of(
            "PRIMARY", "UNIQUE", "KEY", "INDEX", "CONSTRAINT", "FOREIGN", "CHECK");

    private final Map<String, Set<String>> tables;

    public TableSchemaRegistry() {
        this.tables = parseSchemaSql(loadSchemaSql());
        log.info("TableSchemaRegistry loaded {} tables from schema.sql", tables.size());
    }

    TableSchemaRegistry(String schemaSql) {
        this.tables = parseSchemaSql(schemaSql);
    }

    /** 表是否存在于注册表（小写）。 */
    public boolean hasTable(String table) {
        return table != null && tables.containsKey(table.toLowerCase(Locale.ROOT));
    }

    /** 表的列集合（小写）；未知表返回空集。 */
    public Set<String> columnsOf(String table) {
        if (table == null) {
            return Set.of();
        }
        return tables.getOrDefault(table.toLowerCase(Locale.ROOT), Set.of());
    }

    /** 某表是否包含指定列（小写比较）。 */
    public boolean hasColumn(String table, String column) {
        return column != null && columnsOf(table).contains(column.toLowerCase(Locale.ROOT));
    }

    public Map<String, Set<String>> allTables() {
        return tables;
    }

    // ---------------------------------------------------------------------
    // 解析实现
    // ---------------------------------------------------------------------

    static Map<String, Set<String>> parseSchemaSql(String sql) {
        Map<String, Set<String>> result = new LinkedHashMap<>();
        String cleaned = stripComments(sql);
        int idx = 0;
        while (idx < cleaned.length()) {
            int createIdx = cleaned.toUpperCase(Locale.ROOT).indexOf("CREATE TABLE", idx);
            if (createIdx < 0) {
                break;
            }
            int parenIdx = cleaned.indexOf('(', createIdx);
            if (parenIdx < 0) {
                break;
            }
            String header = cleaned.substring(createIdx + "CREATE TABLE".length(), parenIdx).trim();
            String tableName = extractTableName(header);
            if (tableName == null) {
                idx = parenIdx + 1;
                continue;
            }
            int closeIdx = findClosingParen(cleaned, parenIdx);
            if (closeIdx < 0) {
                break;
            }
            String body = cleaned.substring(parenIdx + 1, closeIdx);
            result.put(tableName.toLowerCase(Locale.ROOT), extractColumns(body));
            idx = closeIdx + 1;
        }
        return result;
    }

    static String extractTableName(String header) {
        // header 是 "CREATE TABLE" 之后到 "(" 之间的内容："IF NOT EXISTS name" 或 "name"
        String[] parts = header.trim().split("\\s+");
        if (parts.length == 0) {
            return null;
        }
        String last = parts[parts.length - 1].replace("`", "");
        String upper = last.toUpperCase(Locale.ROOT);
        if (upper.equals("IF") || upper.equals("NOT") || upper.equals("EXISTS")) {
            return null;
        }
        return last;
    }

    static Set<String> extractColumns(String body) {
        Set<String> columns = new LinkedHashSet<>();
        for (String segment : splitTopLevel(body)) {
            String def = segment.trim();
            if (def.isEmpty()) {
                continue;
            }
            String name = firstToken(def);
            if (name == null || NON_COLUMN_KEYWORDS.contains(name.toUpperCase(Locale.ROOT))) {
                continue; // INDEX / PRIMARY KEY / UNIQUE / CONSTRAINT 等约束行
            }
            // 形如 "name TYPE ..."；无类型（纯约束）跳过
            String rest = def.substring(name.length()).trim();
            if (rest.isEmpty() || isTypeToken(firstToken(rest))) {
                columns.add(name.toLowerCase(Locale.ROOT));
            }
        }
        return columns;
    }

    private static boolean isTypeToken(String token) {
        if (token == null) {
            return false;
        }
        String upper = token.toUpperCase(Locale.ROOT);
        return upper.startsWith("VARCHAR") || upper.startsWith("CHAR")
                || upper.startsWith("INT") || upper.startsWith("BIGINT")
                || upper.startsWith("TINYINT") || upper.startsWith("SMALLINT")
                || upper.startsWith("DECIMAL") || upper.startsWith("NUMERIC")
                || upper.startsWith("DOUBLE") || upper.startsWith("FLOAT")
                || upper.startsWith("TEXT") || upper.startsWith("JSON")
                || upper.startsWith("DATETIME") || upper.startsWith("TIMESTAMP")
                || upper.startsWith("DATE") || upper.startsWith("TIME")
                || upper.startsWith("BOOLEAN") || upper.startsWith("BLOB")
                || upper.startsWith("LONGTEXT") || upper.startsWith("MEDIUMTEXT")
                || upper.startsWith("TINYTEXT");
    }

    /** 按顶层逗号切分表体（忽略括号与单引号内的逗号；单引号内 '' 为转义）。 */
    static List<String> splitTopLevel(String body) {
        List<String> parts = new java.util.ArrayList<>();
        int depth = 0;
        boolean inQuote = false;
        StringBuilder current = new StringBuilder();
        for (int i = 0; i < body.length(); i++) {
            char c = body.charAt(i);
            if (inQuote) {
                current.append(c);
                if (c == '\'') {
                    if (i + 1 < body.length() && body.charAt(i + 1) == '\'') {
                        current.append('\''); // 转义单引号
                        i++;
                    } else {
                        inQuote = false;
                    }
                }
                continue;
            }
            switch (c) {
                case '\'' -> {
                    inQuote = true;
                    current.append(c);
                }
                case '(' -> {
                    depth++;
                    current.append(c);
                }
                case ')' -> {
                    depth--;
                    current.append(c);
                }
                case ',' -> {
                    if (depth == 0) {
                        parts.add(current.toString());
                        current.setLength(0);
                    } else {
                        current.append(c);
                    }
                }
                default -> current.append(c);
            }
        }
        if (!current.toString().isBlank()) {
            parts.add(current.toString());
        }
        return parts;
    }

    private static int findClosingParen(String text, int openIdx) {
        int depth = 0;
        boolean inQuote = false;
        for (int i = openIdx; i < text.length(); i++) {
            char c = text.charAt(i);
            if (inQuote) {
                if (c == '\'') {
                    if (i + 1 < text.length() && text.charAt(i + 1) == '\'') {
                        i++;
                    } else {
                        inQuote = false;
                    }
                }
                continue;
            }
            if (c == '\'') {
                inQuote = true;
            } else if (c == '(') {
                depth++;
            } else if (c == ')') {
                depth--;
                if (depth == 0) {
                    return i;
                }
            }
        }
        return -1;
    }

    static String stripComments(String sql) {
        StringBuilder sb = new StringBuilder(sql.length());
        int i = 0;
        int n = sql.length();
        while (i < n) {
            char c = sql.charAt(i);
            if (c == '-' && i + 1 < n && sql.charAt(i + 1) == '-') {
                while (i < n && sql.charAt(i) != '\n') {
                    i++;
                }
            } else if (c == '/' && i + 1 < n && sql.charAt(i + 1) == '*') {
                i += 2;
                while (i + 1 < n && !(sql.charAt(i) == '*' && sql.charAt(i + 1) == '/')) {
                    i++;
                }
                i += 2;
            } else {
                sb.append(c);
                i++;
            }
        }
        return sb.toString();
    }

    private static String firstToken(String s) {
        String trimmed = s.trim();
        if (trimmed.isEmpty()) {
            return null;
        }
        int end = 0;
        while (end < trimmed.length() && !Character.isWhitespace(trimmed.charAt(end)) && trimmed.charAt(end) != '(') {
            end++;
        }
        return trimmed.substring(0, end);
    }

    private static String upperOf(String s) {
        return s.toUpperCase(Locale.ROOT);
    }

    private static String loadSchemaSql() {
        try {
            return new String(new ClassPathResource("schema.sql").getInputStream().readAllBytes(),
                    StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new IllegalStateException("Failed to load schema.sql for TableSchemaRegistry", e);
        }
    }
}
