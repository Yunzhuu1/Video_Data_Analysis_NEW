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
        memory_hit_threshold: float = 0.92  # 混合检索标定（2026-08-18 实测）
        memory_inject_threshold: float = 0.82  # 混合检索标定（2026-08-18 实测）
        memory_namespace: str = "default"
        ark_base_url: str = "https://ark.cn-beijing.volces.com"
        ark_api_key: str = ""
        ark_embedding_model: str = ""  # 方舟 doubao-embedding Model ID（控制台开通后填入）
        memory_lance_path: str = "memory.lance"
        memory_store_backend: str = "lance"  # lance | sqlite（记忆存储后端，lance 需 lancedb + ark key）
        memory_fusion_weight: float = 0.7   # 混合检索融合权重 w（D4 公式）
        memory_vector_dim: int = 2048       # doubao-embedding-vision 实测维度
        memory_alias_fingerprint: bool = False  # 指标 ID 表达指纹（可选增强，标定后启用）
        metric_recall_mode: str = "topk"  # topk | full（full 用于 A/B 基线与紧急回滚）
        metric_recall_top_k: int = 5
        metric_recall_lexical_threshold: float = 0.55
        lineage_planning_mode: str = "active"  # off | shadow | active
        lineage_max_candidates: int = 5
        lineage_max_hops: int = 2
        lineage_max_retries: int = 1
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
            self.memory_hit_threshold = float(os.getenv("MEMORY_HIT_THRESHOLD", "0.92"))
            self.memory_inject_threshold = float(os.getenv("MEMORY_INJECT_THRESHOLD", "0.82"))
            self.memory_namespace = os.getenv("MEMORY_NAMESPACE", "default")
            self.ark_base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com")
            self.ark_api_key = os.getenv("ARK_API_KEY", "")
            self.ark_embedding_model = os.getenv("ARK_EMBEDDING_MODEL", "")
            self.memory_lance_path = os.getenv("MEMORY_LANCE_PATH", "memory.lance")
            self.memory_store_backend = os.getenv("MEMORY_STORE_BACKEND", "lance")
            self.memory_fusion_weight = float(os.getenv("MEMORY_FUSION_WEIGHT", "0.7"))
            self.memory_vector_dim = int(os.getenv("MEMORY_VECTOR_DIM", "2048"))
            self.memory_alias_fingerprint = _env_bool("MEMORY_ALIAS_FINGERPRINT", False)
            self.metric_recall_mode = os.getenv("METRIC_RECALL_MODE", "topk")
            self.metric_recall_top_k = int(os.getenv("METRIC_RECALL_TOP_K", "5"))
            self.metric_recall_lexical_threshold = float(
                os.getenv("METRIC_RECALL_LEXICAL_THRESHOLD", "0.55")
            )
            self.lineage_planning_mode = os.getenv("LINEAGE_PLANNING_MODE", "active")
            self.lineage_max_candidates = int(os.getenv("LINEAGE_MAX_CANDIDATES", "5"))
            self.lineage_max_hops = int(os.getenv("LINEAGE_MAX_HOPS", "2"))
            self.lineage_max_retries = int(os.getenv("LINEAGE_MAX_RETRIES", "1"))
            self.eval_llm_cassette = os.getenv("EVAL_LLM_CASSETTE", "cassettes/default.json")


settings = Settings()
