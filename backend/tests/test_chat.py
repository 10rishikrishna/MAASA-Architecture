from tests.helpers import auth_header


class TestChat:
    def _create_analysis(self, client, token):
        res = client.post(
            "/api/v1/analyze",
            json={"business_problem": "Build an e-commerce platform with microservices"},
            headers=auth_header(token),
        )
        return res.json()["id"]

    def test_send_message(self, client, test_user):
        aid = self._create_analysis(client, test_user["token"])
        res = client.post(
            f"/api/v1/chat/{aid}/send",
            json={"content": "Why did you choose microservices?"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 200
        data = res.json()
        assert "response" in data
        assert "follow_up_suggestions" in data
        assert data["conversation_length"] == 2

    def test_chat_history(self, client, test_user):
        aid = self._create_analysis(client, test_user["token"])
        client.post(
            f"/api/v1/chat/{aid}/send",
            json={"content": "What about costs?"},
            headers=auth_header(test_user["token"]),
        )
        res = client.get(f"/api/v1/chat/{aid}/history", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        messages = res.json()["messages"]
        assert len(messages) == 2  # user + assistant

    def test_clear_chat(self, client, test_user):
        aid = self._create_analysis(client, test_user["token"])
        client.post(
            f"/api/v1/chat/{aid}/send",
            json={"content": "Hello"},
            headers=auth_header(test_user["token"]),
        )
        res = client.post(f"/api/v1/chat/{aid}/clear", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        # Verify cleared
        res = client.get(f"/api/v1/chat/{aid}/history", headers=auth_header(test_user["token"]))
        assert res.json()["messages"] == []

    def test_chat_nonexistent_analysis(self, client, test_user):
        res = client.post(
            "/api/v1/chat/fake-id/send",
            json={"content": "Hello"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 404

    def test_chat_unauthorized(self, client, test_user, second_user):
        aid = self._create_analysis(client, test_user["token"])
        res = client.post(
            f"/api/v1/chat/{aid}/send",
            json={"content": "Hello"},
            headers=auth_header(second_user["token"]),
        )
        assert res.status_code == 404
