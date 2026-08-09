from tests.helpers import auth_header


class TestAuditLogs:
    def test_list_empty(self, client, test_user):
        res = client.get("/api/v1/audit-logs", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        assert res.json() == []

    def test_list_unauthorized(self, client):
        res = client.get("/api/v1/audit-logs")
        assert res.status_code == 401

    def test_list_with_skip_limit(self, client, test_user):
        res = client.get("/api/v1/audit-logs?skip=0&limit=10", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
