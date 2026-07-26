from tests.conftest import auth_header


class TestRegister:
    def test_register_success(self, client):
        res = client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "pass123456",
            "name": "New User",
        })
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["email"] == "new@example.com"
        assert data["name"] == "New User"
        assert data["plan"] == "free"

    def test_register_duplicate_email(self, client, test_user):
        res = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "pass123456",
            "name": "Another User",
        })
        assert res.status_code == 409

    def test_register_invalid_email(self, client):
        res = client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "pass123456",
            "name": "User",
        })
        assert res.status_code == 422


class TestLogin:
    def test_login_success(self, client, test_user):
        res = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["user_id"] == test_user["id"]

    def test_login_wrong_password(self, client, test_user):
        res = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert res.status_code == 401

    def test_login_nonexistent_user(self, client):
        res = client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "pass123",
        })
        assert res.status_code == 401


class TestProfile:
    def test_get_me(self, client, test_user):
        res = client.get("/api/v1/auth/me", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"

    def test_get_me_unauthorized(self, client):
        res = client.get("/api/v1/auth/me")
        assert res.status_code == 401

    def test_update_profile(self, client, test_user):
        res = client.patch(
            "/api/v1/auth/me",
            json={"name": "Updated Name"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Updated Name"

    def test_change_password(self, client, test_user):
        res = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "testpass123", "new_password": "newpass456"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_change_password_wrong_current(self, client, test_user):
        res = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "wrongold", "new_password": "newpass456"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 400
