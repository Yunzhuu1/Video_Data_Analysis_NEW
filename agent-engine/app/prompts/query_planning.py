import json

QUERY_PLANNING_SKILL_VERSION = "query-planning-v1"

QUERY_PLANNING_SYSTEM_PROMPT = """你是受约束的 Query Planner。你只能从候选中复制 selected_plan_id。
禁止输出 SQL、表、列、JOIN、path ID，禁止修改 ResolvedIntent。
普通问题优先低 costTier；明确实时/最新时优先 freshness=REALTIME。
仅返回 JSON：selected_plan_id, reason_code, explanation, confidence。
reason_code 只能是 LOW_COST、REALTIME_REQUIRED、VALIDATION_RETRY。"""


def build_query_planning_prompt(question, intent, candidates, feedback=None) -> str:
    return json.dumps({
        "question": question,
        "resolved_intent": intent,
        "candidates": candidates,
        "validation_feedback": feedback,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
