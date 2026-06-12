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


settings = Settings()
