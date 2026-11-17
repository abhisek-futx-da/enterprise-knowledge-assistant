from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Enterprise Knowledge Assistant"
    database_url: str = "sqlite:///./data/app.db"
    redis_url: str | None = None  # None -> in-process cache (local dev / tests)

    jwt_secret: str = "change-me-in-production-please-32b"
    jwt_algorithm: str = "HS256"
    jwt_audience: str = "knowledge-assistant"
    jwt_expire_minutes: int = 60
    admin_emails: str = ""  # comma-separated; these accounts get the admin role on register

    llm_provider: str = "groq"  # groq | nvidia | gemini | openai | anthropic | ollama
    llm_model: str = "openai/gpt-oss-120b"
    llm_temperature: float = 0.0
    llm_reasoning_effort: str | None = None  # low | medium | high, for reasoning models (gpt-oss); fewer tokens when low
    llm_max_retries: int = 6  # free tiers rate-limit per minute; the client backs off and retries on 429
    groq_api_key: str | None = None
    nvidia_api_key: str | None = None
    google_api_key: str | None = None

    embedding_provider: str = "fastembed"  # fastembed | openai | hash
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    chunk_size: int = 800  # characters
    chunk_overlap: int = 120
    top_k: int = 5
    rrf_k: int = 60
    # Best cosine below this -> refuse without calling the LLM. Calibrated for bge-small on eval/ (run_eval
    # prints the in/out-of-scope gap); re-calibrate when the embedding model or corpus changes.
    min_relevance: float = 0.55
    groundedness_check: bool = True
    max_attempts: int = 2

    max_upload_mb: int = 10
    rate_limit_per_minute: int = 30
    answer_cache_ttl: int = 600

    mcp_server_url: str = "http://localhost:8001/mcp"
    upload_dir: str = "./data/uploads"

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
