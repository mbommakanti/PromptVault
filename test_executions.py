from unittest.mock import patch

import pytest

from config import get_settings
from conftest import API_PREFIX, TestingSessionLocal, create_and_login
from models import Execution
from provider_errors import ProviderAuthenticationError, ProviderTimeoutError
from schemas import AdapterResponse


def _fake_adapter_result(**overrides):
    defaults = {
        "model_response": "Hello there!",
        "model_name": "gpt-4o-mini-2024-07-18",
        "response_status": "completed",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "incomplete_reason": None,
        "response_id": "resp_fake123",
        "temperature": 0.7,
        "max_tokens": 200,
    }
    defaults.update(overrides)
    return AdapterResponse(**defaults)


def test_execute_prompt_success_maps_content_to_instructions(client, auth_headers):
    """Also verifies the PromptVersion.content -> instructions, request.input
    -> input mapping decided on for the adapter call.
    """
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Execution Test", "content": "You are a pirate."},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch("llm_provider.open_ai_adapter", return_value=_fake_adapter_result()) as mock_adapter:
        response = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Describe your ship."},
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["output"] == "Hello there!"
    assert data["status"] == "completed"

    _, call_kwargs = mock_adapter.call_args
    assert call_kwargs["instructions"] == "You are a pirate."
    assert call_kwargs["input"] == "Describe your ship."


def test_execute_prompt_requires_auth(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Auth Required", "content": "content here"},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    response = client.post(
        f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
        json={"input": "Say hi please."},
    )
    assert response.status_code == 401


def test_execute_prompt_not_found(client, auth_headers):
    with patch("llm_provider.open_ai_adapter") as mock_adapter:
        response = client.post(
            f"{API_PREFIX}/prompts/99999/versions/1/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )
    assert response.status_code == 404
    mock_adapter.assert_not_called()


def test_execute_prompt_forbidden_for_non_owner_unpublished_prompt(client, auth_headers):
    other_headers = create_and_login(client, "executionsotheruser1")
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Not Yours", "content": "content here"},
        headers=other_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch("llm_provider.open_ai_adapter") as mock_adapter:
        response = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )
    assert response.status_code == 403
    mock_adapter.assert_not_called()


def test_execute_published_prompt_allowed_for_non_owner(client, auth_headers):
    other_headers = create_and_login(client, "executionsotheruser2")
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Published One", "content": "content here"},
        headers=other_headers,
    )
    prompt_id = create_resp.json()["id"]
    client.patch(f"{API_PREFIX}/prompts/{prompt_id}/publish", headers=other_headers)

    with patch("llm_provider.open_ai_adapter", return_value=_fake_adapter_result()):
        response = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )
    assert response.status_code == 201


def test_execute_prompt_version_not_found(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Version Missing", "content": "content here"},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch("llm_provider.open_ai_adapter") as mock_adapter:
        response = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/99/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )
    assert response.status_code == 404
    mock_adapter.assert_not_called()


def test_execute_prompt_rejects_input_below_min_length(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Validation Test", "content": "content here"},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch("llm_provider.open_ai_adapter") as mock_adapter:
        response = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "hi"},
            headers=auth_headers,
        )
    assert response.status_code == 422
    mock_adapter.assert_not_called()


def test_execute_unexpected_non_provider_error_does_not_persist_execution(client, auth_headers):
    """A genuinely unexpected exception (a bug, not a classified provider
    failure) is NOT a ProviderError, so it is never caught by the router's
    except clause - it still falls straight through to the generic 500
    handler and persists nothing. This is permanent behavior, not a gap
    Step 3 closes: only classified ProviderError failures get persisted
    (see the failure-taxonomy tests below).
    """
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Failure Test", "content": "content here"},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch("llm_provider.open_ai_adapter", side_effect=RuntimeError("provider exploded")), pytest.raises(RuntimeError):
        client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )

    db = TestingSessionLocal()
    try:
        assert db.query(Execution).count() == 0
    finally:
        db.close()


def test_execute_terminal_provider_error_persists_failure_without_retry(client, auth_headers):
    """Auth failures are terminal - open_ai_adapter should only be called
    once, and the failure row + HTTP response should reflect that.
    """
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Terminal Failure Test", "content": "content here"},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch(
        "llm_provider.open_ai_adapter", side_effect=ProviderAuthenticationError("bad key")
    ) as mock_adapter:
        response = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )

    assert response.status_code == 503
    assert mock_adapter.call_count == 1

    db = TestingSessionLocal()
    try:
        execution = db.query(Execution).one()
        assert execution.status == "auth_error"
        assert execution.retry_attempts == 1
        assert execution.output is None
        assert execution.input_tokens is None
        assert execution.output_tokens is None
        assert execution.total_tokens is None
        assert execution.provider_response_id is None
    finally:
        db.close()


def test_execute_retryable_error_exhausts_attempts_then_persists_failure(client, auth_headers):
    """A retryable error (timeout) should be retried up to the configured
    bound, not once and not forever, then persisted with the real attempt
    count once the budget is exhausted.
    """
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Exhausted Retry Test", "content": "content here"},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]
    max_attempts = get_settings().openai_retry_max_attempts

    with patch(
        "llm_provider.open_ai_adapter", side_effect=ProviderTimeoutError("timed out")
    ) as mock_adapter, patch("llm_provider.time.sleep"):
        response = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )

    assert response.status_code == 504
    assert mock_adapter.call_count == max_attempts

    db = TestingSessionLocal()
    try:
        execution = db.query(Execution).one()
        assert execution.status == "timeout"
        assert execution.retry_attempts == max_attempts
    finally:
        db.close()


def test_execute_success_after_retry_persists_real_attempt_count(client, auth_headers):
    """Regression lock: execute_with_retry returns (response, attempts) - the
    router must unpack both and persist the real attempt count, not silently
    default to 1 on a success that needed a retry first.
    """
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Retry Then Success Test", "content": "content here"},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch(
        "llm_provider.open_ai_adapter",
        side_effect=[ProviderTimeoutError("timed out"), _fake_adapter_result()],
    ), patch("llm_provider.time.sleep"):
        response = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )

    assert response.status_code == 201
    assert response.json()["retry_attempts"] == 2


def test_execute_failure_resolves_requested_config_without_swapping_fields(client, auth_headers):
    """Regression lock: temperature and max_tokens must land in their own
    columns on a failure row, not each other's - resolve_execution_config's
    return order is (model, temperature, max_tokens), which previously got
    mismatched against build_execution_object's (model_name, temperature,
    max_tokens) parameter order.
    """
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Config Resolution Test", "content": "content here"},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]
    settings = get_settings()

    with patch("llm_provider.open_ai_adapter", side_effect=ProviderAuthenticationError("bad key")):
        response = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Say hi please.", "max_tokens": 500},
            headers=auth_headers,
        )

    assert response.status_code == 503

    db = TestingSessionLocal()
    try:
        execution = db.query(Execution).one()
        assert execution.max_tokens == 500
        assert execution.temperature == settings.openai_default_temperature
    finally:
        db.close()


def test_get_execution_success_for_owner(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Inspect Me", "content": "You are a pirate."},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch("llm_provider.open_ai_adapter", return_value=_fake_adapter_result()):
        execute_resp = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Describe your ship."},
            headers=auth_headers,
        )
    execution_id = execute_resp.json()["id"]

    response = client.get(f"{API_PREFIX}/executions/{execution_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == execution_id
    assert data["input"] == "Describe your ship."
    assert data["output"] == "Hello there!"
    assert data["status"] == "completed"
    assert data["model_name"] == "gpt-4o-mini-2024-07-18"
    assert data["temperature"] == 0.7
    assert data["max_tokens"] == 200


def test_get_execution_requires_auth(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Auth Required", "content": "content here"},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch("llm_provider.open_ai_adapter", return_value=_fake_adapter_result()):
        execute_resp = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )
    execution_id = execute_resp.json()["id"]

    response = client.get(f"{API_PREFIX}/executions/{execution_id}")
    assert response.status_code == 401


def test_get_execution_not_found(client, auth_headers):
    response = client.get(f"{API_PREFIX}/executions/99999", headers=auth_headers)
    assert response.status_code == 404


def test_get_execution_forbidden_for_non_owner_even_if_prompt_published(client, auth_headers):
    """The executor, not the prompt owner, controls read access to an
    execution's input/output - publishing a prompt does not expose what
    other people privately sent it or got back.
    """
    other_headers = create_and_login(client, "getexecutionotheruser1")
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Published By Other", "content": "content here"},
        headers=other_headers,
    )
    prompt_id = create_resp.json()["id"]
    client.patch(f"{API_PREFIX}/prompts/{prompt_id}/publish", headers=other_headers)

    # auth_headers' user executes the published prompt owned by other_headers' user.
    with patch("llm_provider.open_ai_adapter", return_value=_fake_adapter_result()):
        execute_resp = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )
    execution_id = execute_resp.json()["id"]

    # The prompt owner did not run this execution and must not be able to read it.
    response = client.get(f"{API_PREFIX}/executions/{execution_id}", headers=other_headers)
    assert response.status_code == 403
