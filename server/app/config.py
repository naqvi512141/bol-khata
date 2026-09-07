"""App configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings from env. See docs/04-stack.md §3 and .env.example."""

    # --- ASR ---
    ASR_ENGINE: str = "groq"  # groq | local
    GROQ_API_KEY: str = ""

    # --- LLM fallback ---
    LLM_PROVIDER: str = "groq"  # groq | gemini | model_studio | none
    LLM_MODEL: str = "qwen/qwen3-32b"
    GEMINI_API_KEY: str = ""
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    # --- app ---
    SHOP_ID: str = "demo_shop_01"
    LOG_DIR: str = "./logs"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    """Return a Settings instance. Cached at module level for the demo."""
    return Settings()
