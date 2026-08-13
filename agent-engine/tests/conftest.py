"""Test isolation: keep the suite hermetic regardless of agent-engine/.env.

agent-engine/.env may contain a real AI_API_KEY (used by the running server).
Without this fixture, tests that drive the real graph would inherit that key
and make real LLM calls (nondeterministic, network-dependent, slow).

Forcing eval_llm_mode="mock" makes LLMClient.enabled() return False, so the
graph uses the deterministic fallback paths — exactly what the suite did before
the key was configured.
"""
import pytest

from app.settings import settings


@pytest.fixture(autouse=True)
def hermetic_llm_mode():
    settings.eval_llm_mode = "mock"
    yield
