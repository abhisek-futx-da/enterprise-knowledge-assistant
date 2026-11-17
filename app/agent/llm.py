import json
import re
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ValidationError

from app.config import get_settings

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@lru_cache
def get_llm() -> BaseChatModel:
    """The one chat-model client for the app; provider swaps happen here and nowhere else."""
    s = get_settings()
    if s.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=s.llm_model, temperature=s.llm_temperature, max_retries=2, timeout=60)
    if s.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic  # pip install langchain-anthropic

        return ChatAnthropic(model=s.llm_model, temperature=s.llm_temperature, max_retries=2)
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
