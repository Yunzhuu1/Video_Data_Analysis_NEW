package com.yunzhu.video_data_analysis.semantic;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class SemanticModelTest {

    @Test
    void classifiesTableTypes() {
        assertThat(TableType.classify("user_behavior_fact")).isEqualTo(TableType.FACT);
        assertThat(TableType.classify("play_detail")).isEqualTo(TableType.FACT);
        assertThat(TableType.classify("metric_daily")).isEqualTo(TableType.AGGREGATE);
        assertThat(TableType.classify("content_dim")).isEqualTo(TableType.DIM);
        assertThat(TableType.classify("user_dim")).isEqualTo(TableType.DIM);
        assertThat(TableType.classify("unknown_table")).isNull();
        assertThat(TableType.classify(null)).isNull();
    }

    @Test
    void sensitiveColumnsDetectUserId() {
        assertThat(SensitiveColumns.isSensitive("user_id")).isTrue();
        assertThat(SensitiveColumns.isSensitive("USER_ID")).isTrue();
        assertThat(SensitiveColumns.isSensitive("total_plays")).isFalse();
        assertThat(SensitiveColumns.isSensitive("id")).isFalse();
    }
}
