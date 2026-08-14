package com.yunzhu.video_data_analysis.semantic;

import java.util.Locale;
import java.util.Set;

/**
 * 敏感列清单：SELECT 命中即触发审批（APPROVAL_NEEDED）。
 * 当前以 user_id 起步，后续按业务扩展。
 */
public final class SensitiveColumns {

    private static final Set<String> SENSITIVE = Set.of("user_id");

    private SensitiveColumns() {
    }

    public static boolean isSensitive(String column) {
        return column != null && SENSITIVE.contains(column.toLowerCase(Locale.ROOT));
    }

    public static Set<String> all() {
        return SENSITIVE;
    }
}
