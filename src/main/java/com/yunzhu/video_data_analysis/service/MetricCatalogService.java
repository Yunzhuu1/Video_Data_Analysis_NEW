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
            + "dimensions, time_granularity, source_table, time_field, "
            + "fact_formula, fact_event_filter, owner, version, status "
            + "FROM metric_definition WHERE status = 'ACTIVE'";

    private static final String INSERT_SQL = """
            INSERT INTO metric_definition
              (metric_name, metric_code, business_definition, formula, dimensions,
               time_granularity, source_table, time_field, fact_formula, fact_event_filter,
               version, status)
            VALUES (?, ?, ?, ?, CAST(? AS JSON), ?, ?, ?, ?, ?, 1, 'ACTIVE')
            """;

    private static final String UPDATE_SQL = """
            UPDATE metric_definition
            SET metric_name=?, business_definition=?, formula=?, dimensions=CAST(? AS JSON),
                time_granularity=?, source_table=?, time_field=?, fact_formula=?,
                fact_event_filter=?, status='ACTIVE', version=version+1
            WHERE metric_code=?
            """;

    private final JdbcTemplate jdbcTemplate;

    public MetricCatalogService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<MetricDefinitionDto> listAll() {
        return jdbcTemplate.query(BASE_SQL + " ORDER BY id", (rs, i) -> map(rs));
    }

    public List<MetricDefinitionDto> listAllIncludingInactive() {
        String sql = BASE_SQL.replace(" WHERE status = 'ACTIVE'", "") + " ORDER BY id";
        return jdbcTemplate.query(sql, (rs, i) -> map(rs));
    }

    public void insertManaged(MetricCatalogResource.ManagedMetric metric) {
        jdbcTemplate.update(INSERT_SQL,
                metric.metricName(), metric.metricCode(), metric.businessDefinition(), metric.formula(),
                metric.dimensions(), metric.timeGranularity(), metric.sourceTable(), metric.timeField(),
                metric.factFormula(), metric.factEventFilter());
    }

    public void updateManaged(MetricCatalogResource.ManagedMetric metric) {
        jdbcTemplate.update(UPDATE_SQL,
                metric.metricName(), metric.businessDefinition(), metric.formula(), metric.dimensions(),
                metric.timeGranularity(), metric.sourceTable(), metric.timeField(), metric.factFormula(),
                metric.factEventFilter(), metric.metricCode());
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
