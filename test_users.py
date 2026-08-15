from conftest import API_PREFIX

def test_signup_success(client, test_user_data):
    response = client.post(f"{API_PREFIX}/users/signup", json=test_user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == test_user_data["username"]
    assert data["email"] == test_user_data["email"]
    assert "hashed_password" not in data  # never leak the hash


def test_signup_duplicate_username_or_email_fails(client, test_user_data):
    client.post(f"{API_PREFIX}/users/signup", json=test_user_data)
    response = client.post(f"{API_PREFIX}/users/signup", json=test_user_data)
    assert response.status_code == 400


def test_login_success_returns_token(client, test_user_data):
    client.post(f"{API_PREFIX}/users/signup", json=test_user_data)
    response = client.post(
        f"{API_PREFIX}/users/token",
        data={
            "username": test_user_data["username"],
            "password": test_user_data["password"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password_fails(client, test_user_data):
    client.post(f"{API_PREFIX}/users/signup", json=test_user_data)
    response = client.post(
        f"{API_PREFIX}/users/token",
        data={"username": test_user_data["username"], "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_login_nonexistent_user_fails(client):
    response = client.post(
        f"{API_PREFIX}/users/token",
        data={"username": "nosuchuser", "password": "whatever123"},
    )
    assert response.status_code == 401