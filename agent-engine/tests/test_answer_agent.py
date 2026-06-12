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
