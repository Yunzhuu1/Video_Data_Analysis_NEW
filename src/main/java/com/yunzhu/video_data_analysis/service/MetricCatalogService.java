package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.MetricDefinitionDto;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;

/** 指标字典服务：查询 metric_definition 表，支撑语义解析与确定性合成。 */
@Service
public class MetricCatalogService {

    private static final Logger log = LoggerFactory.getLogger(MetricCatalogService.class);

    private static final String BASE_SQL =
            "SELECT id, metric_name, metric_code, business_definition, formula, "
            + "dimensions, time_granularity, source_table, time_field, owner, version, status "
            + "FROM metric_definition WHERE status = 'ACTIVE'";

    private final JdbcTemplate jdbcTemplate;

    public MetricCatalogService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<MetricDefinitionDto> listAll() {
        return jdbcTemplate.query(BASE_SQL + " ORDER BY id", (rs, i) -> map(rs));
    }

    public MetricDefinitionDto findByCode(String metricCode) {
        List<MetricDefinitionDto> rows = jdbcTemplate.query(
                BASE_SQL + " AND metric_code = ?", (rs, i) -> map(rs), metricCode);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public List<MetricDefinitionDto> search(String keyword) {
        String like = "%" + keyword + "%";
        return jdbcTemplate.query(
                BASE_SQL + " AND (metric_name LIKE ? OR metric_code LIKE ? OR business_definition LIKE ?)",
                (rs, i) -> map(rs), like, like, like);
    }

    private static MetricDefinitionDto map(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new MetricDefinitionDto(
                rs.getLong("id"),
                rs.getString("metric_name"),
                rs.getString("metric_code"),
                rs.getString("business_definition"),
                rs.getString("formula"),
                rs.getString("dimensions"),
                rs.getString("time_granularity"),
                rs.getString("source_table"),
                rs.getString("time_field"),
                rs.getString("fact_formula"),
                rs.getString("fact_event_filter"),
                rs.getString("owner"),
                rs.getInt("version"),
                rs.getString("status"));
    }
}
