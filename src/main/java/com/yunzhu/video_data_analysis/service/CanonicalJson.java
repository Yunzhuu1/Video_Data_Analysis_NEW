package com.yunzhu.video_data_analysis.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Java/Python 共用的受限 canonical JSON profile。 */
public final class CanonicalJson {

    private CanonicalJson() {}

    public static byte[] bytes(ObjectMapper mapper, JsonNode value) {
        rejectUnsupportedNumbers(value);
        try {
            return mapper.writeValueAsBytes(canonicalize(mapper, value));
        } catch (Exception e) {
            throw new IllegalArgumentException("cannot canonicalize JSON", e);
        }
    }

    public static String sha256(ObjectMapper mapper, JsonNode value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes(mapper, value));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    public static String string(ObjectMapper mapper, JsonNode value) {
        return new String(bytes(mapper, value), StandardCharsets.UTF_8);
    }

    private static JsonNode canonicalize(ObjectMapper mapper, JsonNode value) {
        if (value.isObject()) {
            ObjectNode result = mapper.createObjectNode();
            List<String> names = new ArrayList<>();
            value.fieldNames().forEachRemaining(names::add);
            names.sort(CanonicalJson::compareCodePoints);
            for (String name : names) {
                result.set(name, canonicalize(mapper, value.get(name)));
            }
            return result;
        }
        if (value.isArray()) {
            ArrayNode result = mapper.createArrayNode();
            value.forEach(item -> result.add(canonicalize(mapper, item)));
            return result;
        }
        return value.deepCopy();
    }

    private static int compareCodePoints(String left, String right) {
        int[] l = left.codePoints().toArray();
        int[] r = right.codePoints().toArray();
        int length = Math.min(l.length, r.length);
        for (int i = 0; i < length; i++) {
            int compared = Integer.compare(l[i], r[i]);
            if (compared != 0) {
                return compared;
            }
        }
        return Integer.compare(l.length, r.length);
    }

    private static void rejectUnsupportedNumbers(JsonNode value) {
        if (value.isFloatingPointNumber() || value.isBigInteger()) {
            throw new IllegalArgumentException("canonical JSON only permits signed 64-bit integers");
        }
        if (value.isIntegralNumber()) {
            value.longValue();
        }
        value.forEach(CanonicalJson::rejectUnsupportedNumbers);
    }
}
