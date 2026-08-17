import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover - used by minimal eval environments.
    BaseSettings = None
    SettingsConfigDict = None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


if BaseSettings is not None:
    class Settings(BaseSettings):
        service_name: str = "agent-engine"
        platform_base_url: str = "http://localhost:8080"
        internal_api_token: str = "dev-internal-token"
        trace_callback_enabled: bool = True
        platform_calls_enabled: bool = True
        ai_base_url: str = "https://api.deepseek.com"
        ai_api_key: str = ""
        ai_model: str = "deepseek-chat"
        checkpoint_db_path: str = "checkpoints.sqlite"
        eval_llm_mode: str = "real"  # real | record | replay | mock
        memory_db_path: str = "memory.sqlite"
        memory_enabled: bool = True
        memory_hit_threshold: float = 0.95
        memory_inject_threshold: float = 0.85
        memory_namespace: str = "default"
        eval_llm_cassette: str = "cassettes/default.json"

        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
else:
    class Settings:
        def __init__(self) -> None:
            self.service_name = os.getenv("SERVICE_NAME", "agent-engine")
            self.platform_base_url = os.getenv("PLATFORM_BASE_URL", "http://localhost:8080")
            self.internal_api_token = os.getenv("INTERNAL_API_TOKEN", "dev-internal-token")
            self.trace_callback_enabled = _env_bool("TRACE_CALLBACK_ENABLED", True)
            self.platform_calls_enabled = _env_bool("PLATFORM_CALLS_ENABLED", True)
            self.ai_base_url = os.getenv("AI_BASE_URL", "https://api.deepseek.com")
            self.ai_api_key = os.getenv("AI_API_KEY", "")
            self.ai_model = os.getenv("AI_MODEL", "deepseek-chat")
            self.checkpoint_db_path = os.getenv("CHECKPOINT_DB_PATH", "checkpoints.sqlite")
            self.eval_llm_mode = os.getenv("EVAL_LLM_MODE", "real")
            self.memory_db_path = os.getenv("MEMORY_DB_PATH", "memory.sqlite")
            self.memory_enabled = _env_bool("MEMORY_ENABLED", True)
            self.memory_hit_threshold = float(os.getenv("MEMORY_HIT_THRESHOLD", "0.95"))
            self.memory_inject_threshold = float(os.getenv("MEMORY_INJECT_THRESHOLD", "0.85"))
            self.memory_namespace = os.getenv("MEMORY_NAMESPACE", "default")
            self.eval_llm_cassette = os.getenv("EVAL_LLM_CASSETTE", "cassettes/default.json")


settings = Settings()
