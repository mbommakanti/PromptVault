from unittest.mock import patch

from conftest import API_PREFIX, create_and_login
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

    assert response.status_code == 200
    data = response.json()
    assert data["model_response"] == "Hello there!"
    assert data["response_status"] == "completed"

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
    assert response.status_code == 200


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
