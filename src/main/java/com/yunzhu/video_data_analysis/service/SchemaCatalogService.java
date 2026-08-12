package com.yunzhu.video_data_analysis.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 动态加载数据库 Schema 并缓存。
 * <p>
 * 从 INFORMATION_SCHEMA 加载表、字段（含枚举值/JSON 标记）与外键关系。
 * 替代旧 {@code SchemaAgent} 的 LLM 裁剪部分：本服务只做确定性加载，
 * 按问题返回完整 schema 文本（语义裁剪由后续 semantic-resolve 阶段负责）。
 */
@Service
public class SchemaCatalogService {

    private static final Logger log = LoggerFactory.getLogger(SchemaCatalogService.class);

    private static final long CACHE_TTL_MS = 300_000; // 5 分钟

    private final JdbcTemplate jdbcTemplate;

    private String cachedSchema;
    private long lastRefreshMs = 0;

    public SchemaCatalogService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /** 返回与问题相关的 schema 文本（当前返回完整缓存 schema）。 */
    public String relevantSchema(String question) {
        refreshIfStale();
        return cachedSchema == null ? "" : cachedSchema;
    }

    /** 强制刷新 Schema 缓存，由 /admin 接口触发。 */
    public synchronized void refresh() {
        refreshSchema();
    }

    private synchronized void refreshIfStale() {
        if (System.currentTimeMillis() - lastRefreshMs > CACHE_TTL_MS) {
            refreshSchema();
        }
    }

    private synchronized void refreshSchema() {
        try {
            StringBuilder sb = new StringBuilder();

            List<Map<String, Object>> columns = jdbcTemplate.queryForList(
                    "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT "
                    + "FROM INFORMATION_SCHEMA.COLUMNS "
                    + "WHERE TABLE_SCHEMA = 'video_data_analysis' "
                    + "ORDER BY TABLE_NAME, ORDINAL_POSITION");

            Map<String, List<Map<String, Object>>> grouped = columns.stream()
                    .collect(Collectors.groupingBy(m -> (String) m.get("TABLE_NAME")));

            for (var entry : grouped.entrySet()) {
                String table = entry.getKey();
                sb.append(table).append(":");
                for (var col : entry.getValue()) {
                    String colName = (String) col.get("COLUMN_NAME");
                    String colType = (String) col.get("COLUMN_TYPE");
                    sb.append(colName);
                    if (colType != null && colType.startsWith("enum(")) {
                        String values = colType.substring(5, colType.length() - 1).replace("'", "");
                        sb.append("(").append(values).append(")");
                    }
                    if (colType != null && colType.contains("json")) {
                        sb.append("(JSON)");
                    }
                    sb.append(",");
                }
                sb.setLength(sb.length() - 1);
                sb.append("\n");
            }

            List<Map<String, Object>> fks = jdbcTemplate.queryForList(
                    "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
                    + "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                    + "WHERE TABLE_SCHEMA = 'video_data_analysis' AND REFERENCED_TABLE_NAME IS NOT NULL");

            if (!fks.isEmpty()) {
                sb.append("关联:");
                for (var fk : fks) {
                    sb.append(fk.get("TABLE_NAME")).append(".").append(fk.get("COLUMN_NAME"))
                      .append("=").append(fk.get("REFERENCED_TABLE_NAME")).append(".").append(fk.get("REFERENCED_COLUMN_NAME"))
                      .append(" | ");
                }
                sb.setLength(sb.length() - 3);
            }

            cachedSchema = sb.toString();
            lastRefreshMs = System.currentTimeMillis();
            log.debug("Schema refreshed: {} tables, {} chars", grouped.size(), cachedSchema.length());
        } catch (Exception e) {
            log.error("Failed to load schema from INFORMATION_SCHEMA, using last known", e);
            if (cachedSchema == null) {
                cachedSchema = "数据库表结构加载失败";
            }
        }
    }
}
