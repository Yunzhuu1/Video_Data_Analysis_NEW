package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.SqlGateResult;
import com.yunzhu.video_data_analysis.semantic.TableSchemaRegistry;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** 门禁静态层规则测试（计划层桩为通过）。 */
class SqlGateServiceTest {

    private final SqlGateService gate = new SqlGateService(
            new SqlStaticAnalyzer(new TableSchemaRegistry()),
            (sql, tables) -> null);

    private SqlGateResult eval(String sql) {
        return gate.evaluate(sql, false, null, null);
    }

    private SqlGateResult eval(String sql, String intent, String intentTimeRangeType) {
        return gate.evaluate(sql, false, intent, intentTimeRangeType);
    }

    @Test
    void approvalOverrideWithAllowHighRiskPasses() {
        // D8 审批放行不变式（Java 侧防御语义）：allowHighRisk=true 时 APPROVAL_NEEDED → PASS
        SqlGateResult r = gate.evaluate(
                "SELECT user_id FROM user_behavior_fact WHERE created_at > '2023-01-01' LIMIT 10", true, null, null);
        assertThat(r.verdict()).isEqualTo("PASS");
    }

    @Test
    void retryableStillBlocksEvenWithAllowHighRisk() {
        // RETRYABLE（可修复）不因 allowHighRisk 放行——审批只覆盖高风险，不覆盖错误
        SqlGateResult r = gate.evaluate("SELECT * FROM nonexistent_tbl", true, null, null);
        assertThat(r.verdict()).isEqualTo("RETRYABLE");
    }

    @Test
    void passesValidAggregateOnMetricDaily() {
        String sql = "SELECT md.category AS category, SUM(total_plays) AS total_plays "
                + "FROM metric_daily md GROUP BY md.category";
        assertThat(eval(sql).verdict()).isEqualTo("PASS");
    }

    @Test
    void passesAggregateFullScanOnMetricDailyAtStaticLayer() {
        // 聚合表全扫的"放行"由计划层（Stage 3）负责；静态层必须放行
        String sql = "SELECT * FROM metric_daily";
        assertThat(eval(sql).verdict()).isEqualTo("PASS");
    }

    @Test
    void rejectsEmpty() {
        assertThat(eval("   ").code()).isEqualTo("SQL_EMPTY");
        assertThat(eval("   ").verdict()).isEqualTo("RETRYABLE");
    }

    @Test
    void rejectsNonSelect() {
        assertThat(eval("DELETE FROM metric_daily").code()).isEqualTo("SQL_NOT_SELECT");
    }

    @Test
    void rejectsParseError() {
        assertThat(eval("SELECT FROM WHERE").code()).isEqualTo("SQL_PARSE_ERROR");
    }

    @Test
    void rejectsUnknownTable() {
        SqlGateResult r = eval("SELECT * FROM nonexistent_tbl");
        assertThat(r.verdict()).isEqualTo("RETRYABLE");
        assertThat(r.code()).isEqualTo("SQL_UNKNOWN_TABLE");
    }

    @Test
    void rejectsUnknownColumnWithAlias() {
        SqlGateResult r = eval("SELECT ubf.bogus_col FROM user_behavior_fact ubf "
                + "WHERE event_type = 'play' AND timestamp > '2023-01-01' LIMIT 10");
        assertThat(r.verdict()).isEqualTo("RETRYABLE");
        assertThat(r.code()).isEqualTo("SQL_UNKNOWN_COLUMN");
    }

    @Test
    void approvesDetailWithoutLimit() {
        SqlGateResult r = eval("SELECT * FROM user_behavior_fact WHERE created_at > '2023-01-01'");
        assertThat(r.verdict()).isEqualTo("APPROVAL_NEEDED");
        assertThat(r.code()).isEqualTo("DETAIL_QUERY_WITHOUT_LIMIT");
    }

    @Test
    void approvesDetailWithoutTimeRange() {
        SqlGateResult r = eval("SELECT * FROM user_behavior_fact LIMIT 10");
        assertThat(r.verdict()).isEqualTo("APPROVAL_NEEDED");
        assertThat(r.code()).isEqualTo("DETAIL_QUERY_WITHOUT_TIME_RANGE");
    }

    @Test
    void approvesSensitiveColumn() {
        SqlGateResult r = eval("SELECT user_id FROM user_behavior_fact "
                + "WHERE created_at > '2023-01-01' LIMIT 10");
        assertThat(r.verdict()).isEqualTo("APPROVAL_NEEDED");
        assertThat(r.code()).isEqualTo("SENSITIVE_FIELD_ACCESS");
    }

    @Test
    void approvesSelectStarOnSensitiveTable() {
        SqlGateResult r = eval("SELECT * FROM user_behavior_fact "
                + "WHERE created_at > '2023-01-01' LIMIT 10");
        assertThat(r.verdict()).isEqualTo("APPROVAL_NEEDED");
        assertThat(r.code()).isEqualTo("SENSITIVE_FIELD_ACCESS");
    }

    @Test
    void passesBareColumnSumOnFact() {
        // 合成器事实路径：裸列 value + 别名 ubf
        String sql = "SELECT ubf.content_id AS content, SUM(value) AS total_plays "
                + "FROM user_behavior_fact ubf WHERE event_type = 'play' "
                + "AND timestamp > '2023-01-01' GROUP BY ubf.content_id LIMIT 10";
        assertThat(eval(sql).verdict()).isEqualTo("PASS");
    }

    @Test
    void warnsGroupByNotInSelect() {
        SqlGateResult r = eval("SELECT md.date AS date FROM metric_daily md GROUP BY md.category");
        assertThat(r.verdict()).isEqualTo("RETRYABLE");
        assertThat(r.code()).isEqualTo("SQL_RULE_WARNING");
    }

    @Test
    void approvesSelectStarWithAliasOnSensitiveTable() {
        // F1: 别名形式的 t.* 不得绕过敏感列检查
        SqlGateResult r = eval("SELECT ubf.* FROM user_behavior_fact ubf "
                + "WHERE timestamp > '2023-01-01' LIMIT 10");
        assertThat(r.verdict()).isEqualTo("APPROVAL_NEEDED");
        assertThat(r.code()).isEqualTo("SENSITIVE_FIELD_ACCESS");
    }

    @Test
    void resolvesBareColumnWithSingleAliasedTable() {
        // F2: 单表带别名时裸列应解析到该表（而非恒跳过）
        SqlGateResult r = eval("SELECT SUM(value) AS total_plays FROM user_behavior_fact ubf "
                + "WHERE event_type = 'play' AND timestamp > '2023-01-01' LIMIT 10");
        assertThat(r.verdict()).isEqualTo("PASS");
    }

    @Test
    void detailIntentWithoutTimeRangeApprovesEvenIfSqlCompliant() {
        // R1/1.2: intent=detail 且 time_range.type=none → 无条件审批（即使 SQL 合规）
        SqlGateResult r = eval(
                "SELECT * FROM user_behavior_fact WHERE timestamp > '2023-01-01' LIMIT 10",
                "detail", "none");
        assertThat(r.verdict()).isEqualTo("APPROVAL_NEEDED");
        assertThat(r.code()).isEqualTo("DETAIL_QUERY_WITHOUT_TIME_RANGE");
    }

    @Test
    void detailIntentWithTimeRangeNotUnconditionallyBlocked() {
        // intent=detail 但带时间范围 → 不无条件拦截（走 SQL 检查）
        SqlGateResult r = eval(
                "SELECT content_id FROM user_behavior_fact WHERE timestamp > '2023-01-01' LIMIT 10",
                "detail", "absolute");
        assertThat(r.verdict()).isEqualTo("PASS");
    }

    @Test
    void aggregateIntentExemptsLimitRequirement() {
        // 1.3: 聚合意图/聚合 SQL 无 LIMIT → 不再误伤（时间范围合规则 PASS）
        SqlGateResult r = eval(
                "SELECT AVG(value) FROM user_behavior_fact ubf "
                + "WHERE event_type = 'play' AND timestamp > '2023-01-01'",
                "aggregate", "absolute");
        assertThat(r.verdict()).isEqualTo("PASS");
    }

    @Test
    void aggregateWithoutTimeRangeStillApproves() {
        // 1.4: 聚合但无时间范围 → 时间范围规则仍生效（静态层拦截）
        SqlGateResult r = eval("SELECT AVG(value) FROM user_behavior_fact ubf", "aggregate", "none");
        assertThat(r.verdict()).isEqualTo("APPROVAL_NEEDED");
        assertThat(r.code()).isEqualTo("DETAIL_QUERY_WITHOUT_TIME_RANGE");
    }

    @Test
    void aggregateIntentMismatchedDetailShapeRetryable() {
        // 1.5: 聚合意图但 SQL 为明细形态触碰 FACT → RETRYABLE
        SqlGateResult r = eval(
                "SELECT * FROM user_behavior_fact WHERE timestamp > '2023-01-01' LIMIT 10",
                "aggregate", "absolute");
        assertThat(r.verdict()).isEqualTo("RETRYABLE");
        assertThat(r.code()).isEqualTo("SQL_RULE_WARNING");
    }

    @Test
    void warnsJoinWithoutOn() {
        SqlGateResult r = eval("SELECT * FROM metric_daily md JOIN content_dim cd");
        assertThat(r.verdict()).isEqualTo("RETRYABLE");
        assertThat(r.code()).isEqualTo("SQL_RULE_WARNING");
    }
}
