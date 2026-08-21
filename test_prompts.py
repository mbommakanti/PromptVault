import pytest
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from conftest import API_PREFIX, TestingSessionLocal, create_and_login
from models import Prompt, PromptVersion, User
from routers.prompts import update_prompt as update_prompt_endpoint
from schemas import PromptUpdate


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


def test_create_prompt_leaves_no_orphan_when_version_insert_fails(client, auth_headers):
    """create_prompt must be atomic: if the initial PromptVersion insert fails,
    no Prompt row should be left behind.

    SQLite assigns an unspecified integer primary key as max(existing id) + 1,
    so we can predict the id the about-to-be-created Prompt will receive and
    pre-insert a PromptVersion that collides with it on the (prompt_id,
    version_number) unique constraint. This forces a real IntegrityError
    inside create_prompt's commit, rather than a simulated failure.
    """
    setup_db = TestingSessionLocal()
    next_prompt_id = (setup_db.query(func.max(Prompt.id)).scalar() or 0) + 1
    setup_db.add(PromptVersion(prompt_id=next_prompt_id, version_number=1, content="blocker"))
    setup_db.commit()
    setup_db.close()

    payload = {"title": "Should Not Persist", "content": "some content"}
    # Starlette's ServerErrorMiddleware runs the generic Exception handler
    # (producing the 500 a real client would see) and then re-raises so the
    # error still reaches server logs; TestClient mirrors that by re-raising
    # into the test process, so we assert on the underlying DB exception.
    with pytest.raises(IntegrityError):
        client.post(f"{API_PREFIX}/prompts", json=payload, headers=auth_headers)

    check_db = TestingSessionLocal()
    leftover = check_db.query(Prompt).filter(Prompt.title == "Should Not Persist").all()
    check_db.close()
    assert leftover == [], "orphaned Prompt row found after failed version insert"


def test_content_update_version_bump_ignores_stale_cached_reads(client, auth_headers):
    """The version-number increment inside update_prompt must be computed
    atomically by the database, not from a value read earlier in Python --
    otherwise two edits that both start from the same current_version can
    both compute the same next version_number and collide.

    Calls the real update_prompt function directly (not through hand-rolled
    SQL) with two independent sessions that both load the Prompt row while
    current_version is still 1 -- simulating two request handlers reading
    the row before either commits. SQLAlchemy's identity map keeps each
    session's already-loaded object as-is on a later re-query within that
    same session (no auto-refresh without an expiration/commit boundary in
    between), so writer B's session genuinely still sees current_version==1
    in memory when its call runs, even after writer A has committed.
    """
    create_resp = client.post(
        f"{API_PREFIX}/prompts", json={"title": "Race Test Prompt", "content": "v1 content"}, headers=auth_headers
    )
    prompt_id = create_resp.json()["id"]

    session_a = TestingSessionLocal()
    session_b = TestingSessionLocal()

    user_a = session_a.query(User).filter(User.username == "testuser").first()
    user_b = session_b.query(User).filter(User.username == "testuser").first()

    prompt_a = session_a.query(Prompt).filter(Prompt.id == prompt_id).first()
    prompt_b = session_b.query(Prompt).filter(Prompt.id == prompt_id).first()
    assert prompt_a.current_version == prompt_b.current_version == 1

    # Writer A calls the real endpoint function directly and commits first.
    update_prompt_endpoint(
        prompt_update=PromptUpdate(content="version from writer A"),
        db=session_a,
        current_user=user_a,
        prompt_id=prompt_id,
    )
    session_a.close()

    # Writer B calls the same function next, through a session whose cached
    # Prompt object still reflects current_version == 1.
    update_prompt_endpoint(
        prompt_update=PromptUpdate(content="version from writer B"),
        db=session_b,
        current_user=user_b,
        prompt_id=prompt_id,
    )
    session_b.close()

    versions_resp = client.get(f"{API_PREFIX}/prompts/{prompt_id}/versions", headers=auth_headers)
    version_numbers = sorted(v["version_number"] for v in versions_resp.json())
    assert version_numbers == [1, 2, 3], "writer B's bump collided with writer A's version"