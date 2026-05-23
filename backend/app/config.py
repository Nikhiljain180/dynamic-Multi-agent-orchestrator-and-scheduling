from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    groq_api_key: str = ""
    opencode_api_key: str = ""
    opencode_base_url: str = "https://opencode.ai/zen/v1"
    ollama_base_url: str = "http://host.docker.internal:11434"
    llm_provider: str = "mock"
    llm_model: str = ""
    encryption_key: str = ""
    allow_mock_llm_fallback: bool = False
    telegram_bot_token: str = ""
    telegram_workflow_name: str = "Telegram Support Triage"
    schedule_enabled: bool = True
    schedule_poll_seconds: int = 60
    database_url: str = "postgresql+asyncpg://yuno:yuno@localhost:5432/yuno"
    redis_url: str = "redis://localhost:6379/0"
    tavily_api_key: str = ""
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "yuno-agent-platform"
    demo_workspace: str = "demo_workspace"


settings = Settings()
