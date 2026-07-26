from tests.conftest import auth_header


class TestProjects:
    def test_create_project(self, client, test_user):
        res = client.post(
            "/api/v1/projects",
            json={"name": "My Project", "tags": ["python", "fastapi"]},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "My Project"
        assert data["tags"] == ["python", "fastapi"]
        assert data["visibility"] == "private"

    def test_list_projects_empty(self, client, test_user):
        res = client.get("/api/v1/projects", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert res.json() == []

    def test_list_projects(self, client, test_user):
        client.post("/api/v1/projects", json={"name": "P1"}, headers=auth_header(test_user["token"]))
        client.post("/api/v1/projects", json={"name": "P2"}, headers=auth_header(test_user["token"]))
        res = client.get("/api/v1/projects", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert len(res.json()) == 2

    def test_get_project(self, client, test_user):
        create = client.post("/api/v1/projects", json={"name": "Get Me"}, headers=auth_header(test_user["token"]))
        pid = create.json()["id"]
        res = client.get(f"/api/v1/projects/{pid}", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert res.json()["name"] == "Get Me"

    def test_get_project_not_found(self, client, test_user):
        res = client.get("/api/v1/projects/nonexistent", headers=auth_header(test_user["token"]))
        assert res.status_code == 404

    def test_update_project(self, client, test_user):
        create = client.post("/api/v1/projects", json={"name": "Old Name"}, headers=auth_header(test_user["token"]))
        pid = create.json()["id"]
        res = client.patch(
            f"/api/v1/projects/{pid}",
            json={"name": "New Name", "visibility": "public"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 200
        assert res.json()["name"] == "New Name"
        assert res.json()["visibility"] == "public"

    def test_delete_project(self, client, test_user):
        create = client.post("/api/v1/projects", json={"name": "Delete Me"}, headers=auth_header(test_user["token"]))
        pid = create.json()["id"]
        res = client.delete(f"/api/v1/projects/{pid}", headers=auth_header(test_user["token"]))
        assert res.status_code == 204
        res = client.get(f"/api/v1/projects/{pid}", headers=auth_header(test_user["token"]))
        assert res.status_code == 404

    def test_project_isolation(self, client, test_user, second_user):
        create = client.post("/api/v1/projects", json={"name": "User1 Project"}, headers=auth_header(test_user["token"]))
        pid = create.json()["id"]
        res = client.get(f"/api/v1/projects/{pid}", headers=auth_header(second_user["token"]))
        assert res.status_code == 404
