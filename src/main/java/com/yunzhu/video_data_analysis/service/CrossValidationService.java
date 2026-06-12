package com.yunzhu.video_data_analysis.service;

import com.yunzhu.video_data_analysis.dto.CommentResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/** Cross-validates RAG themes against playback detail facts. */
@Service
public class CrossValidationService {

    private static final Logger log = LoggerFactory.getLogger(CrossValidationService.class);

    private final JdbcTemplate jdbcTemplate;

    public CrossValidationService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public String crossValidate(CommentResult ragResult) {
        if (ragResult == null || ragResult.getThemes() == null || ragResult.getThemes().isEmpty()
                || ragResult.getConfidence() < 0.3) {
            return "";
        }

        try {
            String themes = String.join(" ", ragResult.getThemes());
            StringBuilder sb = new StringBuilder("Playback cross-validation\n");
            sb.append("RAG themes: ").append(themes).append("\n");

            boolean hasAd = themes.contains("广告") || themes.toLowerCase().contains("ad")
                    || themes.contains("卡顿") || themes.toLowerCase().contains("lag");
            boolean hasActivity = themes.contains("活动") || themes.contains("内容")
                    || themes.toLowerCase().contains("campaign") || themes.toLowerCase().contains("content");

            List<Map<String, Object>> dropOffs = jdbcTemplate.queryForList(
                    "SELECT cd.category, ROUND(AVG(pd.drop_off_second)) as avg_drop_off, "
                            + "COUNT(*) as plays, ROUND(AVG(pd.play_duration),0) as avg_duration "
                            + "FROM play_detail pd JOIN content_dim cd ON pd.content_id = cd.content_id "
                            + "GROUP BY cd.category");
            sb.append("Category drop-off distribution:\n");
            for (Map<String, Object> row : dropOffs) {
                sb.append("  ").append(row.get("category"))
                        .append(": avg_drop_off=").append(row.get("avg_drop_off")).append("s")
                        .append(", avg_duration=").append(row.get("avg_duration")).append("s")
                        .append(", plays=").append(row.get("plays")).append("\n");
            }

            if (hasAd) {
                List<Map<String, Object>> adZone = jdbcTemplate.queryForList(
                        "SELECT cd.category, "
                                + "ROUND(COUNT(CASE WHEN pd.drop_off_second BETWEEN 10 AND 25 THEN 1 END) * 100.0 / COUNT(*), 1) as ad_zone_rate "
                                + "FROM play_detail pd JOIN content_dim cd ON pd.content_id = cd.content_id "
                                + "GROUP BY cd.category ORDER BY ad_zone_rate DESC");
                sb.append("Ad zone drop-off rate (10-25s):\n");
                for (Map<String, Object> row : adZone) {
                    sb.append("  ").append(row.get("category"))
                            .append(": ").append(row.get("ad_zone_rate")).append("%\n");
                }
            }

            if (hasActivity) {
                List<Map<String, Object>> activityComparison = jdbcTemplate.queryForList(
                        "SELECT cd.category, "
                                + "AVG(CASE WHEN pd.created_at < '2023-10-08' THEN pd.completion_rate END) as during_comp, "
                                + "AVG(CASE WHEN pd.created_at >= '2023-10-08' THEN pd.completion_rate END) as after_comp "
                                + "FROM play_detail pd JOIN content_dim cd ON pd.content_id = cd.content_id "
                                + "GROUP BY cd.category");
                sb.append("Campaign completion-rate comparison:\n");
                for (Map<String, Object> row : activityComparison) {
                    sb.append("  ").append(row.get("category"))
                            .append(": during=").append(row.get("during_comp"))
                            .append(", after=").append(row.get("after_comp")).append("\n");
                }
            }

            return sb.toString();
        } catch (Exception e) {
            log.warn("Cross-validation query failed: {}", e.getMessage());
            return "";
        }
    }
}
