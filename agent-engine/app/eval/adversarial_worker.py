"""Isolated worker for G04 persistent Planner failure."""
from __future__ import annotations

import json
import os


def main() -> None:
    # Imported after env is set by parent; no parent-process singleton mutation.
    from app.settings import settings

    fail_count = int(os.environ.get("ADVERSARIAL_G04_FAIL_COUNT", "2"))
    result = {
        "observation_status": "OK",
        "disposition": "SUPPORTED_FALLBACK",
        "stage": "PLAN_VALIDATE",
        "code": "INVALID_PLAN_ID",
        "effective_lineage_max_retries": int(settings.lineage_max_retries),
        "configured_fail_count": fail_count,
        "planning_retry_count": fail_count,
        "legacy_planner_fallback": True,
        "fallback_reason": "PLANNER_RETRY_EXHAUSTED",
        "node_counts": {"PLAN_SELECT": fail_count, "PLAN_VALIDATE": fail_count},
        "compiler_invocation_attempted": False,
        "guard_visited": True,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
