from unittest.mock import patch

import pytest

from conftest import API_PREFIX, TestingSessionLocal, create_and_login
from models import Execution
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

    with patch("routers.executions.open_ai_adapter", return_value=_fake_adapter_result()) as mock_adapter:
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
    with patch("routers.executions.open_ai_adapter") as mock_adapter:
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

    with patch("routers.executions.open_ai_adapter") as mock_adapter:
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

    with patch("routers.executions.open_ai_adapter", return_value=_fake_adapter_result()):
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

    with patch("routers.executions.open_ai_adapter") as mock_adapter:
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

    with patch("routers.executions.open_ai_adapter") as mock_adapter:
        response = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "hi"},
            headers=auth_headers,
        )
    assert response.status_code == 422
    mock_adapter.assert_not_called()


def test_execute_failure_does_not_persist_execution(client, auth_headers):
    """Locks in current scope: Step 2 only persists on the success path.
    Failure/error persistence is Step 3's job (failure taxonomy).
    """
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Failure Test", "content": "content here"},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch("routers.executions.open_ai_adapter", side_effect=RuntimeError("provider exploded")), pytest.raises(RuntimeError):
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


def test_get_execution_success_for_owner(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts",
        json={"title": "Inspect Me", "content": "You are a pirate."},
        headers=auth_headers,
    )
    prompt_id = create_resp.json()["id"]

    with patch("routers.executions.open_ai_adapter", return_value=_fake_adapter_result()):
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

    with patch("routers.executions.open_ai_adapter", return_value=_fake_adapter_result()):
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
    with patch("routers.executions.open_ai_adapter", return_value=_fake_adapter_result()):
        execute_resp = client.post(
            f"{API_PREFIX}/prompts/{prompt_id}/versions/1/execute",
            json={"input": "Say hi please."},
            headers=auth_headers,
        )
    execution_id = execute_resp.json()["id"]

    # The prompt owner did not run this execution and must not be able to read it.
    response = client.get(f"{API_PREFIX}/executions/{execution_id}", headers=other_headers)
    assert response.status_code == 403
