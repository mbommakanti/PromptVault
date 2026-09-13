from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from config import get_settings
from llm_provider import open_ai_adapter
from schemas import AdapterResponse


def _fake_openai_response(
    status="completed",
    output_text="Hello from the model.",
    input_tokens=5,
    output_tokens=10,
    incomplete_details=None,
    model="gpt-4o-mini-2024-07-18",
    response_id="resp_fake123",
):
    """A plain object shaped like the OpenAI Responses API's return value,
    exposing only the attributes open_ai_adapter actually reads. Keeps these
    tests independent of the real openai SDK and free of any network call.
    """
    return SimpleNamespace(
        output_text=output_text,
        model=model,
        status=status,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        incomplete_details=incomplete_details,
        id=response_id,
    )


def test_open_ai_adapter_maps_completed_response_correctly():
    fake_client = MagicMock()
    fake_client.responses.create.return_value = _fake_openai_response()

    with patch("llm_provider.get_openai_client", return_value=fake_client):
        result = open_ai_adapter(input="Describe a movie.", instructions="Reply briefly.")

    assert isinstance(result, AdapterResponse)
    assert result.model_response == "Hello from the model."
    assert result.model_name == "gpt-4o-mini-2024-07-18"
    assert result.response_status == "completed"
    assert result.incomplete_reason is None
    assert result.input_tokens == 5
    assert result.output_tokens == 10
    assert result.total_tokens == 15
    assert result.response_id == "resp_fake123"


def test_open_ai_adapter_maps_truncated_response_correctly():
    fake_client = MagicMock()
    fake_client.responses.create.return_value = _fake_openai_response(
        status="incomplete",
        output_tokens=16,
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )

    with patch("llm_provider.get_openai_client", return_value=fake_client):
        result = open_ai_adapter(input="Describe a movie.", instructions="Reply briefly.", max_tokens=16)

    assert result.response_status == "incomplete"
    assert result.incomplete_reason == "max_output_tokens"
    assert result.output_tokens == 16


def test_open_ai_adapter_falls_back_to_settings_defaults_when_not_specified():
    fake_client = MagicMock()
    fake_client.responses.create.return_value = _fake_openai_response()
    settings = get_settings()

    with patch("llm_provider.get_openai_client", return_value=fake_client):
        open_ai_adapter(input="Describe a movie.", instructions="Reply briefly.")

    _, call_kwargs = fake_client.responses.create.call_args
    assert call_kwargs["model"] == settings.openai_default_model
    assert call_kwargs["temperature"] == settings.openai_default_temperature
    assert call_kwargs["max_output_tokens"] == settings.openai_default_max_tokens
    assert call_kwargs["timeout"] == settings.openai_timeout_seconds
    assert call_kwargs["store"] is False


def test_open_ai_adapter_respects_caller_overrides():
    fake_client = MagicMock()
    fake_client.responses.create.return_value = _fake_openai_response()

    with patch("llm_provider.get_openai_client", return_value=fake_client):
        open_ai_adapter(
            input="Describe a movie.",
            instructions="Reply briefly.",
            model="gpt-4o",
            temperature=0.9,
            max_tokens=50,
        )

    _, call_kwargs = fake_client.responses.create.call_args
    assert call_kwargs["model"] == "gpt-4o"
    assert call_kwargs["temperature"] == 0.9
    assert call_kwargs["max_output_tokens"] == 50


def test_open_ai_adapter_rejects_positional_arguments():
    """input/instructions are keyword-only specifically to prevent the two
    same-typed required strings from being silently swapped at the call site.
    """
    with pytest.raises(TypeError):
        open_ai_adapter("Describe a movie.", "Reply briefly.")
