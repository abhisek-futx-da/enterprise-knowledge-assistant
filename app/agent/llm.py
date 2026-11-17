import json
import re
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ValidationError

from app.config import get_settings

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)

# Providers that speak the OpenAI API: one client, a different base URL and key. None = OpenAI itself.
OPENAI_COMPATIBLE = {
    "openai": None,
    "groq": "https://api.groq.com/openai/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
}


@lru_cache
def get_llm() -> BaseChatModel:
    """The one chat-model client for the app; provider swaps happen here and nowhere else."""
    s = get_settings()
    if s.llm_provider in OPENAI_COMPATIBLE:
        from langchain_openai import ChatOpenAI

        key = {"groq": s.groq_api_key, "nvidia": s.nvidia_api_key}.get(s.llm_provider)
        if s.llm_provider != "openai" and not key:
            raise ValueError(f"{s.llm_provider.upper()}_API_KEY is not set")
        extra = {"reasoning_effort": s.llm_reasoning_effort} if s.llm_reasoning_effort else {}
        return ChatOpenAI(
            model=s.llm_model, temperature=s.llm_temperature, max_retries=s.llm_max_retries, timeout=60,
            base_url=OPENAI_COMPATIBLE[s.llm_provider], **({"api_key": key} if key else {}), **extra,
        )
    if s.llm_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not s.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not set")
        return ChatGoogleGenerativeAI(model=s.llm_model, temperature=s.llm_temperature,
                                      max_retries=s.llm_max_retries, timeout=60, google_api_key=s.google_api_key)
    if s.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic  # pip install langchain-anthropic

        return ChatAnthropic(model=s.llm_model, temperature=s.llm_temperature, max_retries=s.llm_max_retries)
    if s.llm_provider == "ollama":
        from langchain_ollama import ChatOllama  # pip install langchain-ollama

        return ChatOllama(model=s.llm_model, temperature=s.llm_temperature)
    raise ValueError(f"Unknown LLM_PROVIDER '{s.llm_provider}'")


async def ask_json[T: BaseModel](llm: BaseChatModel, messages: list[BaseMessage], schema: type[T], default: T) -> T:
    """Provider-agnostic structured output. A malformed reply fails closed to `default`, never crashes."""
    reply = await llm.ainvoke(messages)
    text = reply.content if isinstance(reply.content, str) else json.dumps(reply.content)
    match = _JSON_OBJECT.search(text)
    if not match:
        return default
    try:
        return schema.model_validate_json(match.group(0))
    except ValidationError:
        return default
