from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.models import Agent
from app.services.crypto import decrypt_api_key

PROVIDER_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "groq": "llama-3.1-8b-instant",
    "ollama": "llama3.1",
    "opencode": "deepseek-v4-flash-free",
    "mock": "mock",
}

GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]
OLLAMA_MODELS = ["llama3.1", "llama3.2", "mistral"]
OPENCODE_MODELS = ["deepseek-v4-flash-free"]


class MockChatModel(BaseChatModel):
    """Deterministic responses when LLM_PROVIDER=mock (local dev/tests only)."""

    role: str = "assistant"

    @property
    def _llm_type(self) -> str:
        return "mock"

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatGeneration, ChatResult

        content = _mock_content(self.role, messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    async def _agenerate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop, run_manager, **kwargs)


def _mock_content(role: str, messages: list[BaseMessage]) -> str:
    user_text = ""
    system_text = ""
    for msg in messages:
        if msg.type == "human":
            user_text = str(msg.content)
        elif msg.type == "system":
            system_text = str(msg.content).lower()

    combined = f"{system_text} {user_text}".lower()
    if "brief" in combined or "brief" in role:
        return (
            "Key points:\n"
            "- LangGraph orchestrates multi-agent workflows with conditional routing.\n"
            "- Async messaging and live monitoring improve reliability.\n"
            "- External channels (e.g. Telegram) connect agents to users."
        )
    if "executive" in combined or "summary" in role:
        return (
            "# Executive Summary\n\n"
            "AI agent orchestration platforms use graph-based runtimes like LangGraph to coordinate "
            "specialized agents. Async messaging, guardrails, and live monitoring are essential for "
            "production use. External channels enable real-world user interaction."
        )
    if "triage" in combined or "triage" in role:
        if any(w in user_text.lower() for w in ["bill", "payment", "invoice", "charge"]):
            return "INTENT: billing - confidence 0.92"
        return "INTENT: technical - confidence 0.88"
    if "billing" in combined:
        return "Your billing inquiry is resolved. No outstanding charges. Reference: INV-2024-001."
    if "technical" in combined:
        return "Try restarting the workflow and checking run logs in the monitoring dashboard."
    if "respond" in combined:
        return "Thank you for reaching out! Our team has reviewed your request and we're here to help."
    return f"Processed: {user_text[:200]}"


def resolve_provider(agent: Agent) -> str:
    return (agent.provider or settings.llm_provider or "mock").lower()


def resolve_model(agent: Agent) -> str:
    provider = resolve_provider(agent)
    if agent.model:
        return agent.model
    if settings.llm_model:
        return settings.llm_model
    return PROVIDER_DEFAULT_MODELS.get(provider, "gpt-4o-mini")


def get_platform_api_key(provider: str) -> str:
    if provider == "groq":
        return settings.groq_api_key
    if provider == "opencode":
        return settings.opencode_api_key
    if provider == "openai":
        return settings.openai_api_key
    return ""


def resolve_api_key(agent: Agent, provider: str) -> str:
    if not agent.use_platform_api_key and agent.api_key_encrypted:
        decrypted = decrypt_api_key(agent.api_key_encrypted)
        if decrypted:
            return decrypted
    return get_platform_api_key(provider)


def get_platform_api_key_hint(provider: str) -> str | None:
    key = get_platform_api_key(provider)
    if not key or key.startswith("sk-your"):
        return None
    from app.services.crypto import mask_api_key

    return mask_api_key(key)


def get_chat_model(agent: Agent) -> BaseChatModel:
    provider = resolve_provider(agent)
    model = resolve_model(agent)
    api_key = resolve_api_key(agent, provider)

    if provider == "groq" and api_key:
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.3,
        )

    if provider == "opencode" and api_key:
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=settings.opencode_base_url,
            temperature=0.3,
        )

    if provider == "openai" and api_key and not api_key.startswith("sk-your"):
        return ChatOpenAI(model=model, api_key=api_key, temperature=0.3)

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=model,
                base_url=settings.ollama_base_url,
                temperature=0.3,
            )
        except ImportError as exc:
            raise RuntimeError("Install langchain-ollama for Ollama support") from exc

    if provider == "mock":
        return MockChatModel(role=agent.role.lower())

    raise RuntimeError(
        f"No API key configured for provider '{provider}'. "
        "Set platform keys in .env or assign a per-agent key in the Agents UI."
    )
