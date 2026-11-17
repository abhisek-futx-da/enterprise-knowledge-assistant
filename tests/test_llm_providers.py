import pytest

from app.agent.llm import OPENAI_COMPATIBLE, get_llm
from app.config import get_settings


@pytest.fixture
def settings(monkeypatch):
    s = get_settings()
    get_llm.cache_clear()
    yield lambda **kw: [monkeypatch.setattr(s, k, v) for k, v in kw.items()]
    get_llm.cache_clear()


@pytest.mark.parametrize("provider", ["groq", "nvidia"])
def test_openai_compatible_providers_use_their_own_url_and_key(settings, provider):
    settings(llm_provider=provider, llm_model="some/model", groq_api_key="gsk_test", nvidia_api_key="nvapi_test",
             llm_reasoning_effort="low")
    llm = get_llm()
    assert llm.openai_api_base == OPENAI_COMPATIBLE[provider]
    assert llm.openai_api_key.get_secret_value() == ("gsk_test" if provider == "groq" else "nvapi_test")
    assert llm.reasoning_effort == "low"
    assert llm.max_retries == get_settings().llm_max_retries


@pytest.mark.parametrize("provider,var", [("groq", "GROQ_API_KEY"), ("nvidia", "NVIDIA_API_KEY"), ("gemini", "GOOGLE_API_KEY")])
def test_missing_key_names_the_variable_to_set(settings, provider, var):
    settings(llm_provider=provider, groq_api_key=None, nvidia_api_key=None, google_api_key=None)
    with pytest.raises(ValueError, match=var):
        get_llm()


def test_gemini_gets_its_key(settings):
    settings(llm_provider="gemini", llm_model="gemini-test", google_api_key="AIza_test")
    llm = get_llm()
    assert llm.google_api_key.get_secret_value() == "AIza_test"
    assert llm.model.endswith("gemini-test")
