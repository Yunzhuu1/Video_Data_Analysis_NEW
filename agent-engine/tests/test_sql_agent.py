import pytest

from app.agents.sql_agent import SQLGenerationAgent


class DisabledLLM:
    def enabled(self):
        return False


class FakeLLM:
    def enabled(self):
        return True

    async def complete_json(self, system_prompt, user_prompt):
        assert "SELECT only" in system_prompt
        assert "schema_context" in user_prompt
        return {
            "sql": "SELECT date, total_plays FROM metric_daily LIMIT 10",
            "purpose": "trend query",
            "assumptions": ["use metric_daily"],
            "expectedColumns": ["date", "total_plays"],
        }


@pytest.mark.asyncio
async def test_sql_agent_falls_back_without_llm_key():
    agent = SQLGenerationAgent(DisabledLLM())

    result = await agent.generate(
        question="category trend",
        schema_context="metric_daily(date, category, total_plays)",
        hard_guard_feedback=None,
        execution_feedback=None,
        dq_feedback=None,
        sql_attempts=[],
    )

    assert result["sql"].startswith("SELECT")
    assert result["expectedColumns"] == ["date", "category", "total_plays"]
    assert "LLM disabled" in result["assumptions"][0]


@pytest.mark.asyncio
async def test_sql_agent_returns_normalized_llm_json():
    agent = SQLGenerationAgent(FakeLLM())

    result = await agent.generate(
        question="trend",
        schema_context="metric_daily(date, total_plays)",
        hard_guard_feedback="PASS",
        execution_feedback=None,
        dq_feedback=None,
        sql_attempts=[],
    )

    assert result == {
        "sql": "SELECT date, total_plays FROM metric_daily LIMIT 10",
        "purpose": "trend query",
        "assumptions": ["use metric_daily"],
        "expectedColumns": ["date", "total_plays"],
    }
