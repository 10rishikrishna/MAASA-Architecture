from tests.helpers import auth_header


class TestApiKeys:
    def test_create_key(self, client, test_user):
        res = client.post("/api/v1/api-keys", json={"name": "My Key"}, headers=auth_header(test_user["token"]))
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "My Key"
        assert "full_key" in data
        assert data["full_key"].startswith("mosaic_")

    def test_list_keys(self, client, test_user):
        client.post("/api/v1/api-keys", json={"name": "Key1"}, headers=auth_header(test_user["token"]))
        client.post("/api/v1/api-keys", json={"name": "Key2"}, headers=auth_header(test_user["token"]))
        res = client.get("/api/v1/api-keys", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert len(res.json()) == 2

    def test_revoke_key(self, client, test_user):
        create = client.post("/api/v1/api-keys", json={"name": "Revoke Me"}, headers=auth_header(test_user["token"]))
        kid = create.json()["id"]
        res = client.delete(f"/api/v1/api-keys/{kid}", headers=auth_header(test_user["token"]))
        assert res.status_code == 204
        res = client.get("/api/v1/api-keys", headers=auth_header(test_user["token"]))
        assert len(res.json()) == 0

    def test_revoke_key_not_found(self, client, test_user):
        res = client.delete("/api/v1/api-keys/fake-id", headers=auth_header(test_user["token"]))
        assert res.status_code == 404

    def test_keys_isolated_per_user(self, client, test_user, second_user):
        client.post("/api/v1/api-keys", json={"name": "User1 Key"}, headers=auth_header(test_user["token"]))
        res = client.get("/api/v1/api-keys", headers=auth_header(second_user["token"]))
        assert res.status_code == 200
        assert len(res.json()) == 0
