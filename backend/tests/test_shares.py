from tests.conftest import auth_header


class TestShares:
    def test_create_share(self, client, test_user, second_user):
        proj = client.post("/api/v1/projects", json={"name": "Shared"}, headers=auth_header(test_user["token"]))
        pid = proj.json()["id"]
        res = client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "other@example.com", "permission": "edit"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 201
        data = res.json()
        assert data["shared_with_email"] == "other@example.com"
        assert data["permission"] == "edit"

    def test_share_with_self(self, client, test_user):
        proj = client.post("/api/v1/projects", json={"name": "P"}, headers=auth_header(test_user["token"]))
        pid = proj.json()["id"]
        res = client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "test@example.com"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 400

    def test_share_nonexistent_project(self, client, test_user, second_user):
        res = client.post(
            "/api/v1/projects/fake-id/shares",
            json={"email": "other@example.com"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 404

    def test_list_shares(self, client, test_user, second_user):
        proj = client.post("/api/v1/projects", json={"name": "P"}, headers=auth_header(test_user["token"]))
        pid = proj.json()["id"]
        client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "other@example.com"},
            headers=auth_header(test_user["token"]),
        )
        res = client.get(f"/api/v1/projects/{pid}/shares", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_update_share(self, client, test_user, second_user):
        proj = client.post("/api/v1/projects", json={"name": "P"}, headers=auth_header(test_user["token"]))
        pid = proj.json()["id"]
        share = client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "other@example.com", "permission": "view"},
            headers=auth_header(test_user["token"]),
        )
        sid = share.json()["id"]
        res = client.patch(
            f"/api/v1/projects/{pid}/shares/{sid}",
            json={"permission": "edit"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 200
        assert res.json()["permission"] == "edit"

    def test_revoke_share(self, client, test_user, second_user):
        proj = client.post("/api/v1/projects", json={"name": "P"}, headers=auth_header(test_user["token"]))
        pid = proj.json()["id"]
        share = client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "other@example.com"},
            headers=auth_header(test_user["token"]),
        )
        sid = share.json()["id"]
        res = client.delete(f"/api/v1/projects/{pid}/shares/{sid}", headers=auth_header(test_user["token"]))
        assert res.status_code == 204
        # Verify removed
        res = client.get(f"/api/v1/projects/{pid}/shares", headers=auth_header(test_user["token"]))
        assert len(res.json()) == 0
