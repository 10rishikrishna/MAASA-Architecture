from tests.helpers import auth_header


class TestAnalysisCRUD:
    def test_list_empty(self, client, test_user):
        res = client.get("/api/v1/analyze", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert res.json() == []

    def test_create_analysis(self, client, test_user):
        res = client.post(
            "/api/v1/analyze",
            json={"business_problem": "Build an e-commerce platform"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "processing"
        assert data["business_problem"] == "Build an e-commerce platform"
        assert "id" in data

    def test_create_analysis_unauthorized(self, client):
        res = client.post(
            "/api/v1/analyze",
            json={"business_problem": "Build an e-commerce platform"},
        )
        assert res.status_code == 401

    def test_get_analysis(self, client, test_user):
        create = client.post(
            "/api/v1/analyze",
            json={"business_problem": "Build a chat app"},
            headers=auth_header(test_user["token"]),
        )
        analysis_id = create.json()["id"]
        res = client.get(f"/api/v1/analyze/{analysis_id}", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert res.json()["business_problem"] == "Build a chat app"

    def test_get_analysis_not_found(self, client, test_user):
        res = client.get("/api/v1/analyze/nonexistent-id", headers=auth_header(test_user["token"]))
        assert res.status_code == 404

    def test_list_after_create(self, client, test_user):
        client.post(
            "/api/v1/analyze",
            json={"business_problem": "Project A"},
            headers=auth_header(test_user["token"]),
        )
        client.post(
            "/api/v1/analyze",
            json={"business_problem": "Project B"},
            headers=auth_header(test_user["token"]),
        )
        res = client.get("/api/v1/analyze", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert len(res.json()) == 2

    def test_delete_analysis(self, client, test_user):
        create = client.post(
            "/api/v1/analyze",
            json={"business_problem": "To be deleted"},
            headers=auth_header(test_user["token"]),
        )
        analysis_id = create.json()["id"]
        res = client.delete(f"/api/v1/analyze/{analysis_id}", headers=auth_header(test_user["token"]))
        assert res.status_code == 204
        # Confirm it's gone
        res = client.get(f"/api/v1/analyze/{analysis_id}", headers=auth_header(test_user["token"]))
        assert res.status_code == 404

    def test_delete_analysis_not_found(self, client, test_user):
        res = client.delete("/api/v1/analyze/nonexistent-id", headers=auth_header(test_user["token"]))
        assert res.status_code == 404


class TestAnalysisExport:
    def test_export_not_ready(self, client, test_user):
        create = client.post(
            "/api/v1/analyze",
            json={"business_problem": "Export test"},
            headers=auth_header(test_user["token"]),
        )
        analysis_id = create.json()["id"]
        # Analysis is in 'processing' state, export should fail
        res = client.get(
            f"/api/v1/analyze/{analysis_id}/export?format=markdown",
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 400
