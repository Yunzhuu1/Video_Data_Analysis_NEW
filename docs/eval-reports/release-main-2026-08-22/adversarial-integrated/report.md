# Adversarial System Evaluation

- Profile: `COMPLETED`
- Harness: **PASS**
- System readiness: **FAIL**

- case_coverage: 20/20
- variant_coverage: 3/3
- expected_disposition: 14/20
- unsafe_pass: 0/12
- illegal_plan_rejection: 6/7
- graceful_fallback: 2/3
- recovery_success: 3/3
- r1: 1/4
- audit_completeness: 70/71

## Per execution unit

| Unit | Observation | Disposition | Stage / Code | Unsafe |
|---|---|---|---|---|
| adv_c01 | OK | EXECUTE_SUCCESS | SQL_SYNTHESIZE / PASS | False |
| adv_c02 | OK | SYSTEM_ERROR | SQL_HARD_GUARD / DETAIL_QUERY_WITHOUT_LIMIT | False |
| adv_c03 | OK | SYSTEM_ERROR | SQL_HARD_GUARD / DETAIL_QUERY_WITHOUT_LIMIT | False |
| adv_c04 | OK | SYSTEM_ERROR | SQL_HARD_GUARD / DETAIL_QUERY_WITHOUT_TIME_RANGE | False |
| adv_c05 | OK | SUPPORTED_FALLBACK | SQL_SYNTHESIZE / SYNTHESIS_ERROR | False |
| adv_g01 | OK | SAFE_REJECT | SQL_HARD_GUARD / SQL_NOT_SELECT | False |
| adv_g02 | OK | APPROVAL_REQUIRED | SQL_HARD_GUARD / DETAIL_QUERY_WITHOUT_LIMIT | False |
| adv_g03 | OK | RECOVERED | APPROVAL / PASS | False |
| adv_g04 | OK | SUPPORTED_FALLBACK | PLAN_VALIDATE / INVALID_PLAN_ID | False |
| adv_g05 | OK | RECOVERED | SQL_EXECUTE / EXECUTION_ERROR | False |
| adv_p01 | OK | SAFE_REJECT | PLAN_ENUMERATE / REVERSE_JOIN_NOT_ALLOWED | False |
| adv_p02 | OK | SAFE_REJECT | PLAN_VALIDATE / CANDIDATE_TAMPERED | False |
| adv_p03 | OK | RECOVERED | PLAN_VALIDATE / INVALID_PLAN_ID | False |
| adv_p04 | OK | SAFE_REJECT | PLAN_VALIDATE / CANDIDATE_TAMPERED | False |
| adv_p05::lineage | OK | SAFE_REJECT | PLAN_VALIDATE / SNAPSHOT_INTEGRITY_MISMATCH | False |
| adv_p05::metric | OK | SAFE_REJECT | PLAN_VALIDATE / SNAPSHOT_INTEGRITY_MISMATCH | False |
| adv_p05::schema | OK | SAFE_REJECT | PLAN_VALIDATE / SNAPSHOT_INTEGRITY_MISMATCH | False |
| adv_s01 | OK | EXECUTE_SUCCESS | SEMANTIC_RESOLVE / PASS | False |
| adv_s02 | OK | EXECUTE_SUCCESS | SEMANTIC_RESOLVE / PASS | False |
| adv_s03 | OK | EXECUTE_SUCCESS | SEMANTIC_RESOLVE / PASS | False |
| adv_s04 | OK | APPROVAL_REQUIRED | SQL_HARD_GUARD / APPROVAL_NEEDED | False |
| adv_s05 | OK | SUPPORTED_FALLBACK | SEMANTIC_RESOLVE / UNKNOWN_METRIC | False |
