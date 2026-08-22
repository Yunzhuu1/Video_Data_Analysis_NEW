package com.yunzhu.video_data_analysis.service;

import org.junit.jupiter.api.Test;

import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AgentRunQueryServiceTest {

    @Test
    void temporalAdapterAcceptsJavaTimeJdbcAndNull() {
        LocalDateTime expected = LocalDateTime.of(2023, 10, 31, 12, 30, 5);

        assertThat(AgentRunQueryService.toLocalDateTime(expected)).isEqualTo(expected);
        assertThat(AgentRunQueryService.toLocalDateTime(Timestamp.valueOf(expected))).isEqualTo(expected);
        assertThat(AgentRunQueryService.toLocalDateTime(java.sql.Date.valueOf("2023-10-31")))
                .isEqualTo(LocalDate.of(2023, 10, 31).atStartOfDay());
        assertThat(AgentRunQueryService.toLocalDateTime(null)).isNull();
    }

    @Test
    void temporalAdapterRejectsUnknownTypeWithDiagnostic() {
        assertThatThrownBy(() -> AgentRunQueryService.toLocalDateTime("2023-10-31"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("java.lang.String");
    }
}
