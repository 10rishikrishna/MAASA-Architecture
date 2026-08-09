import pytest
from tests.helpers import auth_header


class TestFullUserFlow:
    """Integration test: complete user journey from registration to analysis."""

    def test_register_login_profile(self, client):
        # Register
        reg = client.post("/api/v1/auth/register", json={
            "email": "flow@test.com", "password": "test1234", "name": "Flow User",
        })
        assert reg.status_code == 201
        token = reg.json()["access_token"]

        # Get profile
        me = client.get("/api/v1/auth/me", headers=auth_header(token))
        assert me.status_code == 200
        assert me.json()["name"] == "Flow User"

        # Update profile
        patch = client.patch("/api/v1/auth/me", json={"name": "Updated"}, headers=auth_header(token))
        assert patch.status_code == 200
        assert patch.json()["name"] == "Updated"

        # Change password
        pw = client.post("/api/v1/auth/change-password", json={
            "current_password": "test1234", "new_password": "newpass123",
        }, headers=auth_header(token))
        assert pw.status_code == 200

        # Login with new password
        login = client.post("/api/v1/auth/login", json={
            "email": "flow@test.com", "password": "newpass123",
        })
        assert login.status_code == 200

    def test_analysis_lifecycle(self, client):
        # Register
        reg = client.post("/api/v1/auth/register", json={
            "email": "analyst@test.com", "password": "pass123", "name": "Analyst",
        })
        token = reg.json()["access_token"]

        # Create analysis
        create = client.post("/api/v1/analyze", json={
            "business_problem": "Build a real-time collaboration tool",
            "scale_estimates": {"users": "50000"},
            "constraints": ["low latency", "WebRTC"],
        }, headers=auth_header(token))
        assert create.status_code == 202
        aid = create.json()["id"]

        # List analyses
        lst = client.get("/api/v1/analyze", headers=auth_header(token))
        assert lst.status_code == 200
        assert len(lst.json()) == 1

        # Get analysis (still processing)
        get = client.get(f"/api/v1/analyze/{aid}", headers=auth_header(token))
        assert get.status_code == 200
        assert get.json()["status"] == "processing"

        # Export should fail while processing
        exp = client.get(f"/api/v1/analyze/{aid}/export", headers=auth_header(token))
        assert exp.status_code == 400

        # Delete
        delete = client.delete(f"/api/v1/analyze/{aid}", headers=auth_header(token))
        assert delete.status_code == 204

    def test_project_with_sharing(self, client):
        # Register two users
        u1 = client.post("/api/v1/auth/register", json={
            "email": "owner@test.com", "password": "pass123", "name": "Owner",
        }).json()
        u2 = client.post("/api/v1/auth/register", json={
            "email": "collab@test.com", "password": "pass123", "name": "Collab",
        }).json()

        # Create project as owner
        proj = client.post("/api/v1/projects", json={
            "name": "Shared Project",
            "tags": ["collab", "test"],
            "visibility": "private",
        }, headers=auth_header(u1["access_token"]))
        assert proj.status_code == 201
        pid = proj.json()["id"]

        # Share with collaborator
        share = client.post(f"/api/v1/projects/{pid}/shares", json={
            "email": "collab@test.com", "permission": "edit",
        }, headers=auth_header(u1["access_token"]))
        assert share.status_code == 201

        # List shares
        shares = client.get(f"/api/v1/projects/{pid}/shares", headers=auth_header(u1["access_token"]))
        assert len(shares.json()) == 1

        # Update share permission
        sid = shares.json()[0]["id"]
        upd = client.patch(f"/api/v1/projects/{pid}/shares/{sid}", json={
            "permission": "view",
        }, headers=auth_header(u1["access_token"]))
        assert upd.status_code == 200
        assert upd.json()["permission"] == "view"

        # Revoke share
        rev = client.delete(f"/api/v1/projects/{pid}/shares/{sid}", headers=auth_header(u1["access_token"]))
        assert rev.status_code == 204

    def test_team_management_flow(self, client):
        # Register two users
        admin = client.post("/api/v1/auth/register", json={
            "email": "admin@test.com", "password": "pass123", "name": "Admin",
        }).json()
        member = client.post("/api/v1/auth/register", json={
            "email": "member@test.com", "password": "pass123", "name": "Member",
        }).json()

        # Create team
        team = client.post("/api/v1/teams", json={"name": "Eng Team"}, headers=auth_header(admin["access_token"]))
        assert team.status_code == 201
        tid = team.json()["id"]

        # Add member
        add = client.post(f"/api/v1/teams/{tid}/members", json={
            "email": "member@test.com", "role": "developer",
        }, headers=auth_header(admin["access_token"]))
        assert add.status_code == 201

        # Get team detail
        detail = client.get(f"/api/v1/teams/{tid}", headers=auth_header(admin["access_token"]))
        assert detail.status_code == 200
        assert detail.json()["member_count"] == 2

        # Update member role
        mid = member["user_id"]
        role_up = client.patch(f"/api/v1/teams/{tid}/members/{mid}", json={
            "role": "viewer",
        }, headers=auth_header(admin["access_token"]))
        assert role_up.status_code == 200
        assert role_up.json()["role"] == "viewer"

        # Remove member
        rem = client.delete(f"/api/v1/teams/{tid}/members/{mid}", headers=auth_header(admin["access_token"]))
        assert rem.status_code == 204

    def test_api_key_lifecycle(self, client):
        # Register
        reg = client.post("/api/v1/auth/register", json={
            "email": "keyuser@test.com", "password": "pass123", "name": "Key User",
        })
        token = reg.json()["access_token"]

        # Create key
        key = client.post("/api/v1/api-keys", json={"name": "prod-key"}, headers=auth_header(token))
        assert key.status_code == 201
        kid = key.json()["id"]
        full_key = key.json()["full_key"]
        assert full_key.startswith("mosaic_")

        # List keys
        keys = client.get("/api/v1/api-keys", headers=auth_header(token))
        assert len(keys.json()) == 1

        # Revoke key
        rev = client.delete(f"/api/v1/api-keys/{kid}", headers=auth_header(token))
        assert rev.status_code == 204

        # Verify gone
        keys2 = client.get("/api/v1/api-keys", headers=auth_header(token))
        assert len(keys2.json()) == 0

    def test_chat_flow(self, client):
        # Register and create analysis
        reg = client.post("/api/v1/auth/register", json={
            "email": "chatter@test.com", "password": "pass123", "name": "Chatter",
        })
        token = reg.json()["access_token"]

        create = client.post("/api/v1/analyze", json={
            "business_problem": "Build a microservices e-commerce platform",
        }, headers=auth_header(token))
        aid = create.json()["id"]

        # Send messages
        msg1 = client.post(f"/api/v1/chat/{aid}/send", json={
            "content": "Why did you choose microservices?",
        }, headers=auth_header(token))
        assert msg1.status_code == 200
        assert "response" in msg1.json()

        msg2 = client.post(f"/api/v1/chat/{aid}/send", json={
            "content": "What about the costs?",
        }, headers=auth_header(token))
        assert msg2.status_code == 200

        # Check history
        hist = client.get(f"/api/v1/chat/{aid}/history", headers=auth_header(token))
        assert len(hist.json()["messages"]) == 4  # 2 user + 2 assistant

        # Clear chat
        clear = client.post(f"/api/v1/chat/{aid}/clear", headers=auth_header(token))
        assert clear.status_code == 200

        hist2 = client.get(f"/api/v1/chat/{aid}/history", headers=auth_header(token))
        assert len(hist2.json()["messages"]) == 0
