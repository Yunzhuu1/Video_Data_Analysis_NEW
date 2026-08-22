# Adversarial System Evaluation

- Profile: `COMPLETED`
- Harness: **PASS**
- System readiness: **FAIL**

- case_coverage: 11/11
- variant_coverage: 3/3
- expected_disposition: 9/11
- unsafe_pass: 3/6
- illegal_plan_rejection: 3/7
- graceful_fallback: 2/2
- recovery_success: 1/1
- r1: 0/0
- audit_completeness: 44/44

## Per execution unit

| Unit | Observation | Disposition | Stage / Code | Unsafe |
|---|---|---|---|---|
| adv_c01 | OK | EXECUTE_SUCCESS | SQL_SYNTHESIZE / PASS | False |
| adv_c02 | OK | EXECUTE_SUCCESS | SQL_SYNTHESIZE / PASS | False |
| adv_c03 | OK | EXECUTE_SUCCESS | SQL_SYNTHESIZE / PASS | False |
| adv_c04 | OK | EXECUTE_SUCCESS | SQL_SYNTHESIZE / PASS | False |
| adv_c05 | OK | SUPPORTED_FALLBACK | SQL_SYNTHESIZE / SYNTHESIS_ERROR | False |
| adv_g01 | PROFILE_INELIGIBLE | - | PROFILE / OFFLINE_INELIGIBLE | False |
| adv_g02 | PROFILE_INELIGIBLE | - | PROFILE / OFFLINE_INELIGIBLE | False |
| adv_g03 | PROFILE_INELIGIBLE | - | PROFILE / OFFLINE_INELIGIBLE | False |
| adv_g04 | OK | SUPPORTED_FALLBACK | PLAN_VALIDATE / INVALID_PLAN_ID | False |
| adv_g05 | PROFILE_INELIGIBLE | - | PROFILE / OFFLINE_INELIGIBLE | False |
| adv_p01 | OK | SAFE_REJECT | PLAN_ENUMERATE / REVERSE_JOIN_NOT_ALLOWED | False |
| adv_p02 | OK | SAFE_REJECT | PLAN_VALIDATE / CANDIDATE_TAMPERED | False |
| adv_p03 | OK | RECOVERED | PLAN_VALIDATE / INVALID_PLAN_ID | False |
| adv_p04 | OK | SAFE_REJECT | PLAN_VALIDATE / CANDIDATE_TAMPERED | False |
| adv_p05::lineage | OK | SYSTEM_ERROR | PLAN_VALIDATE / PASS | True |
| adv_p05::metric | OK | SYSTEM_ERROR | PLAN_VALIDATE / PASS | True |
| adv_p05::schema | OK | SYSTEM_ERROR | PLAN_VALIDATE / PASS | True |
| adv_s01 | PROFILE_INELIGIBLE | - | PROFILE / OFFLINE_INELIGIBLE | False |
| adv_s02 | PROFILE_INELIGIBLE | - | PROFILE / OFFLINE_INELIGIBLE | False |
| adv_s03 | PROFILE_INELIGIBLE | - | PROFILE / OFFLINE_INELIGIBLE | False |
| adv_s04 | PROFILE_INELIGIBLE | - | PROFILE / OFFLINE_INELIGIBLE | False |
| adv_s05 | PROFILE_INELIGIBLE | - | PROFILE / OFFLINE_INELIGIBLE | False |
