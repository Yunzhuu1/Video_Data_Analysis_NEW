package com.yunzhu.video_data_analysis.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.IsoFields;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * 数据初始化器，用测试数据填充 video_data_analysis 数据库。
 * <p>
 * 包含故意设计的业务模式用于智能体分析演示：
 * <ul>
 *   <li>活动激增：10月1-7日，所有播放事件+50%，美食分类+200%</li>
 *   <li>节后下降：10月8-10日，所有播放事件-40%</li>
 * </ul>
 * <p>
 * 如果 user_behavior_fact 已有数据则跳过初始化。
 * 使用固定随机种子 (42) 保证结果可重现。
 */
@Component
@ConditionalOnProperty(prefix = "app.data-initializer", name = "enabled", havingValue = "true")
public class DataInitializer implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(DataInitializer.class);

    private final JdbcTemplate jdbcTemplate;
    private final Random random = new Random(42);

    /* ==================== 维度数据定义 ==================== */

    private static final String[] REGIONS = {"北京", "上海", "广州"};
    private static final String[] GENDERS = {"male", "female"};

    private static final String[][] CREATORS = {
            {"creator_1", "美妆达人小美", "500000", "1200", "1", "美妆"},
            {"creator_2", "游戏主播大壮", "800000", "800", "1", "游戏"},
            {"creator_3", "美食家阿杰", "300000", "600", "0", "美食"}
    };

    /** [id, title, description, tags, duration, creator_id, category, modality, resolution] */
    private static final String[][] CONTENTS = {
            {"content_1", "日常淡妆教程",  "教你如何快速画出自然淡妆",            "[\"美妆\",\"教程\"]",    "120", "creator_1", "美妆", "video", "1080p"},
            {"content_2", "秋冬口红推荐",  "适合秋冬季节的口红试色",              "[\"美妆\",\"口红\",\"试色\"]", "180", "creator_1", "美妆", "video", "1080p"},
            {"content_3", "王者荣耀五杀集锦", "最新版本五杀精彩操作",             "[\"游戏\",\"王者荣耀\",\"五杀\"]", "300", "creator_2", "游戏", "video", "720p"},
            {"content_4", "原神深渊攻略",  "12层深渊满星阵容推荐",               "[\"游戏\",\"原神\",\"攻略\"]",  "240", "creator_2", "游戏", "video", "1080p"},
            {"content_5", "家庭版红烧肉",  "入口即化的红烧肉做法",                "[\"美食\",\"红烧肉\",\"家常菜\"]",  "90", "creator_3", "美食", "video", "1080p"},
            {"content_6", "重庆小面秘方",  "地道重庆小面超详细教程",              "[\"美食\",\"重庆小面\",\"面条\"]", "150", "creator_3", "美食", "video", "1080p"}
    };

    /** [activity_id, start_time, end_time, type, target_content, reward] */
    private static final String[][] ACTIVITIES = {
            {"activity_1", "2023-10-01 00:00:00", "2023-10-07 23:59:59",
                    "挑战赛", "[\"content_5\",\"content_6\"]", "100积分"}
    };

    /** [metric_name, formula, dimension, time_granularity] */
    private static final String[][] METRICS = {
            {"完播率",
             "SUM(CASE WHEN event_type = 'play' THEN value ELSE 0 END) / SUM(c.duration)",
             null, "天"},
            {"互动率",
             "(SUM(CASE WHEN event_type = 'like' THEN 1 ELSE 0 END) + SUM(CASE WHEN event_type = 'comment' THEN 1 ELSE 0 END)) / SUM(CASE WHEN event_type = 'play' THEN 1 ELSE 0 END)",
             null, "天"}
    };

    /* ==================== 运行入口 ==================== */

    public DataInitializer(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public void run(String... args) {
        if (hasData()) {
            log.info("user_behavior_fact 已有数据，跳过初始化");
            return;
        }

        log.info("开始初始化测试数据...");

        insertTimeDim();
        insertUserDim();
        insertCreatorDim();
        insertContentDim();
        insertActivityDim();
        insertMetricDef();
        createMetricDailyTable();
        insertUserBehaviorFact();
        insertMetricDaily();
        createPlayDetailTable();
        insertPlayDetail();

        log.info("测试数据初始化完成");
    }

    /**
     * @return 如果 user_behavior_fact 已包含行则返回true
     */
    private boolean hasData() {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(1) FROM user_behavior_fact", Integer.class);
        return count != null && count > 0;
    }

    /* ==================== 维度表初始化 ==================== */

    private void insertTimeDim() {
        String sql = "INSERT IGNORE INTO time_dim (date, week, month, quarter, year) VALUES (?, ?, ?, ?, ?)";
        List<Object[]> batch = new ArrayList<>();

        LocalDate start = LocalDate.of(2023, 10, 1);
        LocalDate end = LocalDate.of(2023, 10, 31);
        for (LocalDate date = start; !date.isAfter(end); date = date.plusDays(1)) {
            batch.add(new Object[]{
                    java.sql.Date.valueOf(date),
                    date.get(IsoFields.WEEK_OF_WEEK_BASED_YEAR),
                    date.getMonthValue(),
                    (date.getMonthValue() - 1) / 3 + 1,
                    date.getYear()
            });
        }
        jdbcTemplate.batchUpdate(sql, batch);
        log.info("  time_dim: {} days inserted", batch.size());
    }

    private void insertUserDim() {
        String sql = "INSERT IGNORE INTO user_dim (user_id, age, gender, region) VALUES (?, ?, ?, ?)";
        List<Object[]> batch = new ArrayList<>();

        for (int i = 1; i <= 50; i++) {
            batch.add(new Object[]{
                    "user_" + i,
                    18 + random.nextInt(18),
                    GENDERS[random.nextInt(2)],
                    REGIONS[random.nextInt(3)]
            });
        }
        jdbcTemplate.batchUpdate(sql, batch);
        log.info("  user_dim: {} users inserted", batch.size());
    }

    private void insertCreatorDim() {
        String sql = "INSERT IGNORE INTO creator_dim (creator_id, name, followers, following, verified, category) "
                + "VALUES (?, ?, ?, ?, ?, ?)";
        List<Object[]> batch = new ArrayList<>();
        for (String[] c : CREATORS) {
            batch.add(new Object[]{c[0], c[1], Integer.parseInt(c[2]), Integer.parseInt(c[3]),
                    Integer.parseInt(c[4]), c[5]});
        }
        jdbcTemplate.batchUpdate(sql, batch);
        log.info("  creator_dim: {} creators inserted", CREATORS.length);
    }

    private void insertContentDim() {
        String sql = "INSERT IGNORE INTO content_dim (content_id, title, description, tags, duration, "
                + "creator_id, publish_time, category, modality, resolution) "
                + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        List<Object[]> batch = new ArrayList<>();

        for (String[] c : CONTENTS) {
            batch.add(new Object[]{
                    c[0], c[1], c[2], c[3],
                    Integer.parseInt(c[4]),
                    c[5],
                    Timestamp.valueOf(LocalDateTime.of(2023, 9, 20 + random.nextInt(10), 10, 0)),
                    c[6], c[7], c[8]
            });
        }
        jdbcTemplate.batchUpdate(sql, batch);
        log.info("  content_dim: {} videos inserted", batch.size());
    }

    private void insertActivityDim() {
        String sql = "INSERT IGNORE INTO activity_dim (activity_id, start_time, end_time, type, target_content, reward) "
                + "VALUES (?, ?, ?, ?, ?, ?)";
        List<Object[]> batch = new ArrayList<>();
        for (String[] a : ACTIVITIES) {
            batch.add(new Object[]{a[0], a[1], a[2], a[3], a[4], a[5]});
        }
        jdbcTemplate.batchUpdate(sql, batch);
        log.info("  activity_dim: {} activities inserted", ACTIVITIES.length);
    }

    private void insertMetricDef() {
        String sql = "INSERT IGNORE INTO metric_def (metric_name, formula, dimension, time_granularity) "
                + "VALUES (?, ?, CAST(? AS JSON), ?)";

        for (String[] m : METRICS) {
            jdbcTemplate.update(sql, m[0], m[1], m[2], m[3]);
        }
        log.info("  metric_def: {} metrics inserted", METRICS.length);
    }

    /* ==================== 行为事实数据 ==================== */

    private void insertUserBehaviorFact() {
        String sql = "INSERT INTO user_behavior_fact "
                + "(user_id, event_type, timestamp, content_id, creator_id, dimension, value) "
                + "VALUES (?, ?, ?, ?, ?, ?, ?)";

        List<Object[]> batch = new ArrayList<>();

        for (int day = 1; day <= 31; day++) {
            boolean isActivityPeriod = day <= 7;
            boolean isPostHoliday = day >= 8 && day <= 10;

            // 统计每天的事件总数用于日志记录
            int dayEventCount = 0;

            for (int userIdx = 1; userIdx <= 50; userIdx++) {
                String userId = "user_" + userIdx;

                // --- 生成播放事件 ---
                int basePlayCount = 4 + random.nextInt(4); // 4-7 plays baseline
                double playMultiplier = 1.0;

                if (isActivityPeriod) {
                    playMultiplier = 1.5; // 活动期整体 +50%
                } else if (isPostHoliday) {
                    playMultiplier = 0.6; // 节后整体 -40%
                }

                // Track which videos were played today (for generating likes/comments)
                List<Integer> playedContentIndices = new ArrayList<>();

                // Generate plays
                int actualPlays = (int) Math.round(basePlayCount * playMultiplier);
                if (actualPlays < 1) actualPlays = 1;

                for (int p = 0; p < actualPlays; p++) {
                    // Select content with activity-period bias toward food (indices 4,5)
                    int contentIdx = selectContentIndex(isActivityPeriod);
                    String[] content = CONTENTS[contentIdx];
                    String contentId = content[0];
                    String creatorId = content[5];
                    String category = content[6];
                    int duration = Integer.parseInt(content[4]);

                    // 播放值：视频时长的随机百分比，但必须小于时长
                    int playValue = 1 + random.nextInt(duration - 1);

                    LocalDateTime ts = randomTimestamp(2023, 10, day);
                    String dimension = String.format(
                            "{\"category\": \"%s\", \"creator_id\": \"%s\"}", category, creatorId);

                    batch.add(new Object[]{userId, "play", Timestamp.valueOf(ts),
                            contentId, creatorId, dimension, (double) playValue});

                    playedContentIndices.add(contentIdx);
                }

                // --- 生成点赞事件（约30%的播放视频获得点赞）---
                for (int ci : playedContentIndices) {
                    if (random.nextDouble() < 0.3) {
                        String[] content = CONTENTS[ci];
                        String category = content[6];
                        String creatorId = content[5];
                        String dimension = String.format(
                                "{\"category\": \"%s\", \"creator_id\": \"%s\"}", category, creatorId);
                        LocalDateTime ts = randomTimestamp(2023, 10, day);

                        batch.add(new Object[]{userId, "like", Timestamp.valueOf(ts),
                                content[0], creatorId, dimension, 1.0});
                    }
                }

                // --- 生成评论事件（约10%的播放视频获得评论）---
                for (int ci : playedContentIndices) {
                    if (random.nextDouble() < 0.1) {
                        String[] content = CONTENTS[ci];
                        String category = content[6];
                        String creatorId = content[5];
                        String dimension = String.format(
                                "{\"category\": \"%s\", \"creator_id\": \"%s\"}", category, creatorId);
                        LocalDateTime ts = randomTimestamp(2023, 10, day);

                        batch.add(new Object[]{userId, "comment", Timestamp.valueOf(ts),
                                content[0], creatorId, dimension, 1.0});
                    }
                }
            }
        }

        // 执行批量插入
        int[] updateCounts = jdbcTemplate.batchUpdate(sql, batch);
        log.info("  user_behavior_fact: {} events inserted ({} batches)",
                updateCounts.length, batch.size());
    }

    /* ==================== 辅助方法 ==================== */

    /**
     * 选择随机内容索引，可选活动期间偏差。
     * 在活动期间（10月1-7日），美食分类内容（索引4,5）的概率提高3倍。
     */
    private int selectContentIndex(boolean isActivityPeriod) {
        if (isActivityPeriod) {
            // 加权选择：美食（索引4,5）获得3倍权重
            // Weights: non-food = 1, food = 3
            // 所有6个内容的总权重：1+1+1+1+3+3 = 10
            int r = random.nextInt(10);
            if (r < 1) return 0;       // content_1 (美妆)
            if (r < 2) return 1;       // content_2 (美妆)
            if (r < 3) return 2;       // content_3 (游戏)
            if (r < 4) return 3;       // content_4 (游戏)
            if (r < 7) return 4;       // content_5 (美食) - 3x weight
            return 5;                   // content_6 (美食) - 3x weight
        } else {
            // 所有6个内容等概率
            return random.nextInt(6);
        }
    }

    /**
     * 在给定日期内生成随机时间戳，介于08:00和23:59之间。
     */
    private LocalDateTime randomTimestamp(int year, int month, int day) {
        int hour = 8 + random.nextInt(16);   // 8-23
        int minute = random.nextInt(60);     // 0-59
        int second = random.nextInt(60);     // 0-59
        return LocalDateTime.of(year, month, day, hour, minute, second);
    }

    /* ==================== RAG 评论数据 ==================== */

    private void createPlayDetailTable() {
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS play_detail (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    content_id VARCHAR(64) NOT NULL,
                    play_duration INT NOT NULL COMMENT '实际观看时长(秒)',
                    drop_off_second INT COMMENT '跳出时间点(秒)',
                    completion_rate DECIMAL(5,2) COMMENT '完播率',
                    created_at DATETIME NOT NULL
                )
                """);
        log.info("  play_detail: 表已就绪");
    }

    private void insertPlayDetail() {
        // 为每个用户每天的美食类播放生成播放明细
        // 重点：美食类视频广告多(12s插入)，用户跳出集中在12-20秒区间
        String sql = "INSERT IGNORE INTO play_detail (user_id, content_id, play_duration, drop_off_second, completion_rate, created_at) VALUES (?, ?, ?, ?, ?, ?)";
        List<Object[]> batch = new ArrayList<>();

        for (int day = 1; day <= 31; day++) {
            for (int u = 1; u <= 50; u++) {
                String userId = "user_" + u;
                for (int ci = 0; ci < 6; ci++) {
                    if (random.nextDouble() > 0.4) continue; // 60% 概率产生播放明细
                    String contentId = CONTENTS[ci][0];
                    int duration = Integer.parseInt(CONTENTS[ci][4]);
                    boolean isFood = ci >= 4; // content_5, content_6 是美食

                    // 美食视频：广告在12秒，跳出集中在12-20秒
                    // 非美食：无广告或广告在末尾，跳出分布均匀
                    int dropOff;
                    if (isFood) {
                        // 美食视频: 70% 概率在广告点附近跳出
                        dropOff = random.nextDouble() < 0.7
                                ? 12 + random.nextInt(15)  // 12-27秒跳出（第一支广告在12秒）
                                : 10 + random.nextInt(duration - 20);
                    } else {
                        dropOff = 10 + random.nextInt(duration - 20);
                    }

                    int playDuration = Math.min(dropOff + random.nextInt(5), duration);
                    double rate = duration > 0 ? (double) playDuration / duration * 100 : 0;

                    LocalDateTime ts = randomTimestamp(2023, 10, day);
                    batch.add(new Object[]{userId, contentId, playDuration, dropOff,
                            Math.round(rate * 100.0) / 100.0, java.sql.Timestamp.valueOf(ts)});
                }
            }
        }

        try {
            jdbcTemplate.batchUpdate(sql, batch);
            log.info("  play_detail: {} 条播放明细已注入", batch.size());
        } catch (Exception e) {
            log.warn("  play_detail 注入失败: {}", e.getMessage());
        }
    }

    private void createMetricDailyTable() {
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS metric_daily (
                    date DATE NOT NULL,
                    category VARCHAR(32) NOT NULL,
                    total_plays BIGINT DEFAULT 0,
                    total_play_duration DECIMAL(10,2) DEFAULT 0,
                    total_likes BIGINT DEFAULT 0,
                    total_comments BIGINT DEFAULT 0,
                    total_shares BIGINT DEFAULT 0,
                    total_follows BIGINT DEFAULT 0,
                    total_favorites BIGINT DEFAULT 0,
                    PRIMARY KEY (date, category)
                ) COMMENT='每日预聚合指标表'
                """);
        log.info("  metric_daily: 表已就绪");
    }

    private void insertMetricDaily() {
        jdbcTemplate.execute("""
                INSERT IGNORE INTO metric_daily (date, category,
                    total_plays, total_play_duration, total_likes, total_comments)
                SELECT
                    DATE(ubf.timestamp) AS date,
                    cd.category,
                    COUNT(CASE WHEN ubf.event_type = 'play' THEN 1 END) AS total_plays,
                    COALESCE(SUM(CASE WHEN ubf.event_type = 'play' THEN ubf.value ELSE 0 END), 0) AS total_play_duration,
                    COUNT(CASE WHEN ubf.event_type = 'like' THEN 1 END) AS total_likes,
                    COUNT(CASE WHEN ubf.event_type = 'comment' THEN 1 END) AS total_comments
                FROM user_behavior_fact ubf
                JOIN content_dim cd ON ubf.content_id = cd.content_id
                GROUP BY DATE(ubf.timestamp), cd.category
                ORDER BY date, category
                """);
        Integer count = jdbcTemplate.queryForObject("SELECT COUNT(1) FROM metric_daily", Integer.class);
        log.info("  metric_daily: {} 行聚合数据已注入", count);
    }
}
