from tests.helpers import auth_header


class TestTeams:
    def test_create_team(self, client, test_user):
        res = client.post("/api/v1/teams", json={"name": "Dev Team"}, headers=auth_header(test_user["token"]))
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Dev Team"
        assert data["member_count"] == 1

    def test_list_teams(self, client, test_user):
        client.post("/api/v1/teams", json={"name": "T1"}, headers=auth_header(test_user["token"]))
        client.post("/api/v1/teams", json={"name": "T2"}, headers=auth_header(test_user["token"]))
        res = client.get("/api/v1/teams", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert len(res.json()) == 2

    def test_get_team(self, client, test_user):
        create = client.post("/api/v1/teams", json={"name": "My Team"}, headers=auth_header(test_user["token"]))
        tid = create.json()["id"]
        res = client.get(f"/api/v1/teams/{tid}", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "My Team"
        assert len(data["members"]) == 1

    def test_get_team_not_member(self, client, test_user, second_user):
        create = client.post("/api/v1/teams", json={"name": "Private Team"}, headers=auth_header(test_user["token"]))
        tid = create.json()["id"]
        res = client.get(f"/api/v1/teams/{tid}", headers=auth_header(second_user["token"]))
        assert res.status_code == 403

    def test_update_team(self, client, test_user):
        create = client.post("/api/v1/teams", json={"name": "Old"}, headers=auth_header(test_user["token"]))
        tid = create.json()["id"]
        res = client.patch(f"/api/v1/teams/{tid}", json={"name": "New"}, headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert res.json()["name"] == "New"

    def test_delete_team(self, client, test_user):
        create = client.post("/api/v1/teams", json={"name": "Delete Me"}, headers=auth_header(test_user["token"]))
        tid = create.json()["id"]
        res = client.delete(f"/api/v1/teams/{tid}", headers=auth_header(test_user["token"]))
        assert res.status_code == 204

    def test_add_member(self, client, test_user, second_user):
        create = client.post("/api/v1/teams", json={"name": "Team"}, headers=auth_header(test_user["token"]))
        tid = create.json()["id"]
        res = client.post(
            f"/api/v1/teams/{tid}/members",
            json={"email": "other@example.com", "role": "member"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 201
        assert res.json()["email"] == "other@example.com"

    def test_add_member_nonexistent_email(self, client, test_user):
        create = client.post("/api/v1/teams", json={"name": "Team"}, headers=auth_header(test_user["token"]))
        tid = create.json()["id"]
        res = client.post(
            f"/api/v1/teams/{tid}/members",
            json={"email": "ghost@example.com"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 404

    def test_add_member_duplicate(self, client, test_user):
        create = client.post("/api/v1/teams", json={"name": "Team"}, headers=auth_header(test_user["token"]))
        tid = create.json()["id"]
        # Owner is already a member
        res = client.post(
            f"/api/v1/teams/{tid}/members",
            json={"email": "test@example.com"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 409

    def test_add_member_not_admin(self, client, test_user, second_user):
        create = client.post("/api/v1/teams", json={"name": "Team"}, headers=auth_header(test_user["token"]))
        tid = create.json()["id"]
        # Add second_user as a non-admin member
        client.post(
            f"/api/v1/teams/{tid}/members",
            json={"email": "other@example.com", "role": "member"},
            headers=auth_header(test_user["token"]),
        )
        # second_user tries to add another member
        res = client.post(
            f"/api/v1/teams/{tid}/members",
            json={"email": "test@example.com"},
            headers=auth_header(second_user["token"]),
        )
        assert res.status_code == 403

    def test_remove_member(self, client, test_user, second_user):
        create = client.post("/api/v1/teams", json={"name": "Team"}, headers=auth_header(test_user["token"]))
        tid = create.json()["id"]
        client.post(
            f"/api/v1/teams/{tid}/members",
            json={"email": "other@example.com"},
            headers=auth_header(test_user["token"]),
        )
        res = client.delete(
            f"/api/v1/teams/{tid}/members/{second_user['id']}",
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 204
