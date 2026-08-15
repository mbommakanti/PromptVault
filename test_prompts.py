from conftest import API_PREFIX, create_and_login


def test_create_prompt_success(client, auth_headers):
    payload = {"title": "Test Prompt", "content": "Some prompt content here"}
    response = client.post(f"{API_PREFIX}/prompts", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Prompt"
    assert data["current_version"] == 1
    assert data["is_published"] is False


def test_create_prompt_requires_auth(client):
    payload = {"title": "Test Prompt", "content": "Some prompt content here"}
    response = client.post(f"{API_PREFIX}/prompts", json=payload)
    assert response.status_code == 401


def test_list_prompts_shows_only_own_and_published(client, auth_headers):
    other_headers = create_and_login(client, "otheruser1")

    client.post(f"{API_PREFIX}/prompts", json={"title": "My Prompt", "content": "content here"}, headers=auth_headers)
    client.post(
        f"{API_PREFIX}/prompts", json={"title": "Their Private Prompt", "content": "content here"}, headers=other_headers
    )

    response = client.get(f"{API_PREFIX}/prompts", headers=auth_headers)
    titles = [p["title"] for p in response.json()]
    assert "My Prompt" in titles
    assert "Their Private Prompt" not in titles


def test_get_prompt_not_found(client, auth_headers):
    response = client.get(f"{API_PREFIX}/prompts/99999", headers=auth_headers)
    assert response.status_code == 404


def test_get_private_prompt_forbidden_for_non_owner(client, auth_headers):
    other_headers = create_and_login(client, "otheruser2")
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Private Prompt", "content": "content here"}, headers=other_headers
    )
    prompt_id = create_resp.json()["id"]

    response = client.get(f"{API_PREFIX}/prompts/{prompt_id}", headers=auth_headers)
    assert response.status_code == 403


def test_get_published_prompt_visible_to_others(client, auth_headers):
    other_headers = create_and_login(client, "otheruser3")
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Published Prompt", "content": "content here"}, headers=other_headers
    )
    prompt_id = create_resp.json()["id"]
    client.patch(f"{API_PREFIX}/prompts/{prompt_id}/publish", headers=other_headers)

    response = client.get(f"{API_PREFIX}/prompts/{prompt_id}", headers=auth_headers)
    assert response.status_code == 200


def test_update_prompt_content_creates_new_version(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Versioned Prompt", "content": "version 1 content"}, headers=auth_headers
    )
    prompt_id = create_resp.json()["id"]

    update_resp = client.put(
        f"{API_PREFIX}/prompts/{prompt_id}", json={"content": "version 2 content"}, headers=auth_headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["current_version"] == 2

    versions_resp = client.get(f"{API_PREFIX}/prompts/{prompt_id}/versions", headers=auth_headers)
    assert len(versions_resp.json()) == 2


def test_update_prompt_metadata_only_does_not_bump_version(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Original Title", "content": "content here"}, headers=auth_headers
    )
    prompt_id = create_resp.json()["id"]

    update_resp = client.put(
        f"{API_PREFIX}/prompts/{prompt_id}", json={"title": "Updated Title"}, headers=auth_headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Title"
    assert update_resp.json()["current_version"] == 1


def test_update_prompt_forbidden_for_non_owner(client, auth_headers):
    other_headers = create_and_login(client, "otheruser4")
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Not Yours", "content": "content here"}, headers=other_headers
    )
    prompt_id = create_resp.json()["id"]

    response = client.put(
        f"{API_PREFIX}/prompts/{prompt_id}", json={"title": "Hacked Title"}, headers=auth_headers
    )
    assert response.status_code == 403


def test_delete_prompt_soft_deletes_and_hides_it(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "To Be Deleted", "content": "content here"}, headers=auth_headers
    )
    prompt_id = create_resp.json()["id"]

    delete_resp = client.delete(f"{API_PREFIX}/prompts/{prompt_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"{API_PREFIX}/prompts/{prompt_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_delete_prompt_twice_returns_404(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Double Delete", "content": "content here"}, headers=auth_headers
    )
    prompt_id = create_resp.json()["id"]

    client.delete(f"{API_PREFIX}/prompts/{prompt_id}", headers=auth_headers)
    second_delete = client.delete(f"{API_PREFIX}/prompts/{prompt_id}", headers=auth_headers)
    assert second_delete.status_code == 404


def test_delete_prompt_forbidden_for_non_owner(client, auth_headers):
    other_headers = create_and_login(client, "otheruser5")
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Protected Prompt", "content": "content here"}, headers=other_headers
    )
    prompt_id = create_resp.json()["id"]

    response = client.delete(f"{API_PREFIX}/prompts/{prompt_id}", headers=auth_headers)
    assert response.status_code == 403


def test_publish_toggle_flips_both_ways(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Toggle Me Prompt", "content": "content here"}, headers=auth_headers
    )
    prompt_id = create_resp.json()["id"]

    first_toggle = client.patch(f"{API_PREFIX}/prompts/{prompt_id}/publish", headers=auth_headers)
    assert first_toggle.json()["is_published"] is True

    second_toggle = client.patch(f"{API_PREFIX}/prompts/{prompt_id}/publish", headers=auth_headers)
    assert second_toggle.json()["is_published"] is False


def test_get_specific_version_success(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Version Fetch Test", "content": "v1 content"}, headers=auth_headers
    )
    prompt_id = create_resp.json()["id"]

    response = client.get(f"{API_PREFIX}/prompts/{prompt_id}/versions/1", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["content"] == "v1 content"


def test_get_specific_version_not_found(client, auth_headers):
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Version Fetch Test 2", "content": "content here"}, headers=auth_headers
    )
    prompt_id = create_resp.json()["id"]

    response = client.get(f"{API_PREFIX}/prompts/{prompt_id}/versions/99", headers=auth_headers)
    assert response.status_code == 404


def test_create_prompt_with_only_required_fields(client, auth_headers):
    """Confirms description/tags/model_target are genuinely optional."""
    payload = {"title": "Minimal Prompt", "content": "just the basics"}
    response = client.post(f"{API_PREFIX}/prompts", json=payload, headers=auth_headers)
    assert response.status_code == 201