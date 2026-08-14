import json

import pytest

from app.agents.answer_agent import AnswerAgent


class DisabledLLM:
    def enabled(self):
        return False


class FakeLLM:
    def enabled(self):
        return True

    async def complete_json(self, system_prompt, user_prompt):
        assert "query_result" in user_prompt
        assert "Chart fields" in system_prompt
        return {
            "summary": "plays increased",
            "sql": "SELECT date, total_plays FROM metric_daily",
            "metrics": [{"name": "total_plays", "value": 10}],
            "charts": [{"type": "line", "xField": "date", "yField": "total_plays"}],
            "warnings": [],
        }


@pytest.mark.asyncio
async def test_answer_agent_fallback_uses_query_result():
    agent = AnswerAgent(DisabledLLM())

    result = await agent.generate(
        question="trend",
        query_result={
            "columns": ["date", "total_plays"],
            "rows": [{"date": "2026-01-01", "total_plays": 10}],
            "rowCount": 1,
        },
        sql="SELECT date, total_plays FROM metric_daily",
        dq_result=None,
        warnings=["partial data"],
    )

    assert result["summary"].startswith("ChatBI answered")
    assert result["metrics"] == [{"name": "total_plays", "value": 10}]
    assert result["charts"][0]["type"] == "line"
    assert result["warnings"] == ["partial data"]


@pytest.mark.asyncio
async def test_answer_agent_normalizes_llm_json_and_preserves_warnings():
    agent = AnswerAgent(FakeLLM())

    result = await agent.generate(
        question="trend",
        query_result={"columns": ["date", "total_plays"], "rows": [], "rowCount": 0},
        sql="SELECT date, total_plays FROM metric_daily",
        dq_result=None,
        warnings=["dq warning"],
    )

    assert result["summary"] == "plays increased"
    assert result["warnings"] == ["dq warning"]
    assert result["charts"][0]["xField"] == "date"


@pytest.mark.asyncio
async def test_answer_agent_sanitizes_malformed_llm_output():
    class MalformedLLM:
        def enabled(self):
            return True

        async def complete_json(self, system_prompt, user_prompt):
            return {
                "summary": "plays increased",
                "sql": "SELECT 1",
                "metrics": {"total_plays": 100},  # dict 而非 list → 必须安全降级
                "charts": [{"type": "line"}, "not-a-dict"],  # 非 dict 项剔除
                "recommendations": {"bad": "shape"},  # dict 而非 list
            }

    agent = AnswerAgent(MalformedLLM())
    result = await agent.generate(
        question="trend",
        query_result={"columns": ["date"], "rows": [], "rowCount": 0},
        sql="SELECT 1",
        dq_result=None,
        warnings=[],
    )

    assert result["metrics"] == []
    assert result["charts"] == [{"type": "line"}]
    assert result["recommendations"] == []


@pytest.mark.asyncio
async def test_answer_agent_fills_metrics_from_query_result():
    class EmptyMetricsLLM:
        def enabled(self):
            return True

        async def complete_json(self, system_prompt, user_prompt):
            return {
                "summary": "ok",
                "sql": "SELECT 1",
                "metrics": [],  # LLM 没给 metrics
                "charts": [],
                "recommendations": [],
            }

    agent = AnswerAgent(EmptyMetricsLLM())
    result = await agent.generate(
        question="统计各分类总播放量",
        query_result={
            "columns": ["category", "total_plays"],
            "rows": [{"category": "美食", "total_plays": 3828}],
            "rowCount": 1,
        },
        sql="SELECT 1",
        dq_result=None,
        warnings=[],
    )

    assert result["metrics"], "metrics 应被查询结果兜底填充"
    assert any(m["name"] == "total_plays" for m in result["metrics"])


@pytest.mark.asyncio
async def test_answer_agent_merges_dq_warning():
    class FakeLLM2:
        def enabled(self):
            return True

        async def complete_json(self, system_prompt, user_prompt):
            return {"summary": "ok", "sql": "SELECT 1", "metrics": [], "charts": [], "recommendations": []}

    agent = AnswerAgent(FakeLLM2())
    result = await agent.generate(
        question="q",
        query_result={"columns": [], "rows": [], "rowCount": 0},
        sql="SELECT 1",
        dq_result=None,
        warnings=["Result was truncated; answer should mention partial data."],
    )

    assert "partial data" in json.dumps(result, ensure_ascii=False)

