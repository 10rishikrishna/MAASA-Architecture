"""Tests for the canonical architecture model, generator, validation, and chat modification."""
from tests.helpers import auth_header


class TestCanonicalModel:
    def test_new_model_shape(self):
        from backend.agents.model import new_model, ARCHITECTURE_MODEL_VERSION
        m = new_model("Build a todo app", domain="General", architecture_tier="professional", scale_estimates={})
        assert m["version"] == ARCHITECTURE_MODEL_VERSION
        assert m["business_problem"] == "Build a todo app"
        assert m["status"] == "processing"
        # Canonical sections must all exist
        for section in ("requirements", "architecture", "database", "api", "deployment",
                        "security", "performance", "failure_scenarios", "risks", "review", "diagrams"):
            assert section in m

    def test_normalize_component(self):
        from backend.agents.model import normalize_component
        c = normalize_component({"name": "Cart Service", "type": "service", "tech": "Go", "reason": "handles carts"}, 1)
        assert c["name"] == "Cart Service"
        assert c["technology"] == "Go"
        assert c["responsibility"] == "handles carts"
        assert c["internal_or_external"] == "internal"
        # Missing fields are defaulted, not crashed
        c2 = normalize_component({}, 2)
        assert c2["name"]
        assert c2["type"] == "service"

    def test_validate_model_roundtrip_empty(self):
        from backend.agents.model import new_model, validate_model
        m = new_model("Build a todo app")
        issues = validate_model(m)
        assert any(i["severity"] == "error" for i in issues)


class TestGeneratorScenarios:
    """The five mandated validation scenarios."""

    def _model(self, problem, **kw):
        from backend.agents.mock_data import get_mock_analysis
        return get_mock_analysis(problem, **kw)

    def test_crud_must_be_monolithic(self):
        m = self._model("Build a simple todo list CRUD app")
        assert m["architecture"]["pattern"] == "Monolithic Architecture"
        assert m["performance"]["workload"]["complexity_score"] < 25
        comps = m["architecture"]["components"]
        assert not any(c["type"] == "queue" for c in comps)
        assert not any(c["type"] == "cache" for c in comps)

    def test_ecommerce_microservices(self):
        m = self._model("Build an e-commerce platform handling 100,000 orders per hour")
        assert m["architecture"]["pattern"] == "Microservices Architecture"
        assert m["domain"] == "E-Commerce"
        w = m["performance"]["workload"]
        assert w["avg_requests_per_second"] > 0
        assert w["peak_requests_per_second"] >= w["avg_requests_per_second"]

    def test_payment_event_driven(self):
        m = self._model("Build a payment processing system for a bank handling 50,000 transactions per minute")
        assert m["architecture"]["pattern"] == "Event-Driven Microservices"
        assert m["domain"] == "FinTech"
        comps = m["architecture"]["components"]
        assert any(c["type"] == "queue" for c in comps)

    def test_realtime_chat_scale(self):
        m = self._model("Build a real-time chat application for 1 million users")
        assert m["architecture"]["pattern"] == "Event-Driven Microservices"
        assert m["performance"]["workload"]["users"] >= 1_000_000

    def test_ambiguous_input(self):
        m = self._model("Build something")
        assert m["architecture"]["pattern"] == "Monolithic Architecture"
        assert len(m["requirements"]["ambiguities"]) > 0

    def test_social_network_not_cybersecurity(self):
        # Regression: "social" must not be classified via the "soc" keyword.
        m = self._model("Build a social network for 5 million people")
        assert m["domain"] == "General"

    def test_all_scenarios_validate_clean(self):
        from backend.agents.model import validate_model, summarize_validation
        problems = [
            "Build a simple todo list CRUD app",
            "Build an e-commerce platform handling 100,000 orders per hour",
            "Build a payment processing system for a bank handling 50,000 transactions per minute",
            "Build a real-time chat application for 1 million users",
            "Build a social network for 5 million people",
            "Build something",
        ]
        for p in problems:
            summary = summarize_validation(validate_model(self._model(p)))
            assert summary["passes"], f"{p}: {summary['errors']}"

    def test_diagrams_three_levels_consistent_node_maps(self):
        import re
        m = self._model("Build an e-commerce platform handling 100,000 orders per hour")
        for level in ("level1", "level2", "level3"):
            d = m["diagrams"][level]
            assert d["mermaid"]
            assert d["ascii"]
            node_map = d.get("node_map") or {}
            for nid in re.findall(r"click (N\d+)", d["mermaid"]):
                assert nid in node_map, f"{level}: {nid} missing from node_map"
            assert len(node_map) > 1

    def test_performance_is_real_math_not_generic(self):
        from backend.agents.mock_data import _EVENT_REQUEST_FACTOR
        m = self._model("Build a payment processing system for a bank handling 50,000 transactions per minute")
        w = m["performance"]["workload"]
        # Business events are expanded into internal requests (avg = rate x event factor).
        raw_rate = 50_000 / 60
        assert w["avg_requests_per_second"] == round(raw_rate * _EVENT_REQUEST_FACTOR, 2)
        assert w["peak_requests_per_second"] == round(raw_rate * _EVENT_REQUEST_FACTOR * 3, 2)
        assert w["source"]

    def test_story_mode_is_detailed(self):
        m = self._model("Build an e-commerce platform handling 100,000 orders per hour")
        story = m["architecture"]["explanation_modes"]["story"]
        assert len(story) > 1500
        for marker in ("front door", "route", "database", "fallback"):
            assert marker.lower() in story.lower()

    def test_eli5_terms_expanded(self):
        m = self._model("Build a payment processing system for a bank handling 50,000 transactions per minute")
        terms = m["architecture"]["explanation_modes"]["terms"]
        assert len(terms) >= 8
        for t in terms:
            assert t["term"] and t["meaning"] and t["analogy"]
            assert len(t["meaning"]) > 80

    def test_alternatives_include_two_and_three_tier(self):
        m = self._model("Build an e-commerce platform handling 100,000 orders per hour")
        alts = m["architecture"]["alternatives"]
        keys = [a["key"] for a in alts]
        assert "two_tier" in keys and "three_tier" in keys
        assert sum(1 for a in alts if a["recommended"]) == 1
        for a in alts:
            assert a["name"] and len(a["flow"]) >= 5
            assert a["pros"] and a["cons"] and a["when_to_use"]
            assert len(a["components"]) >= 2

    def test_deep_overview_covers_all_facets(self):
        m = self._model("Build an e-commerce platform handling 100,000 orders per hour")
        ov = m["overview_explained"]
        titles = [s["title"].lower() for s in ov]
        assert len(ov) >= 10
        for needle in ("scale", "pattern", "component", "data", "api", "security", "deployment", "performance", "score", "risk", "requirements"):
            assert any(needle in t for t in titles), f"missing facet: {needle}"
        assert all(s["title"] and len(s["paragraphs"]) >= 1 for s in ov)
        total = sum(len(p) for s in ov for p in s["paragraphs"])
        assert total > 5000

    def test_deep_overview_roundtrip_through_legacy(self):
        from backend.agents.model import to_legacy_fields, from_legacy
        m = self._model("Build an e-commerce platform handling 100,000 orders per hour")
        legacy = to_legacy_fields(m)
        rebuilt = from_legacy(
            m["business_problem"],
            requirements=legacy["requirements"],
            architecture_design=legacy["architecture_design"],
            database_schema=legacy["database_schema"],
            api_specification=legacy["api_specification"],
            deployment_config=legacy["deployment_config"],
            security_audit=legacy["security_audit"],
            performance_strategies=legacy["performance_strategies"],
            diagrams=legacy["diagrams"],
        )
        assert len(rebuilt["overview_explained"]) == len(m["overview_explained"])

    def test_alternatives_roundtrip_through_legacy(self):
        from backend.agents.model import to_legacy_fields, from_legacy
        m = self._model("Build an e-commerce platform handling 100,000 orders per hour")
        legacy = to_legacy_fields(m)
        rebuilt = from_legacy(
            m["business_problem"],
            requirements=legacy["requirements"],
            architecture_design=legacy["architecture_design"],
            database_schema=legacy["database_schema"],
            api_specification=legacy["api_specification"],
            deployment_config=legacy["deployment_config"],
            security_audit=legacy["security_audit"],
            performance_strategies=legacy["performance_strategies"],
            diagrams=legacy["diagrams"],
        )
        assert len(rebuilt["architecture"]["alternatives"]) == len(m["architecture"]["alternatives"])


class TestChatModification:
    def _create_analysis(self, client, token):
        res = client.post(
            "/api/v1/analyze",
            json={"business_problem": "Build a simple todo app"},
            headers=auth_header(token),
        )
        return res.json()["id"]

    def test_change_database_persists(self, client, test_user):
        aid = self._create_analysis(client, test_user["token"])
        res = client.post(
            f"/api/v1/chat/{aid}/send",
            json={"content": "change the database to PostgreSQL"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["modification_applied"] is True
        assert "database" in data["modified_sections"]

        detail = client.get(f"/api/v1/analyze/{aid}", headers=auth_header(test_user["token"])).json()
        assert detail["architecture_model"]["database"]["database_type"] == "PostgreSQL"
        # Legacy tab view stays in sync.
        assert detail["database_schema"]["database_type"] == "PostgreSQL"

    def test_no_change_when_already_set(self, client, test_user):
        aid = self._create_analysis(client, test_user["token"])
        client.post(
            f"/api/v1/chat/{aid}/send",
            json={"content": "change the database to PostgreSQL"},
            headers=auth_header(test_user["token"]),
        )
        res = client.post(
            f"/api/v1/chat/{aid}/send",
            json={"content": "change the database to PostgreSQL"},
            headers=auth_header(test_user["token"]),
        )
        data = res.json()
        assert data["modification_applied"] is False
        assert "already" in data["response"].lower()

    def test_add_cache_modification(self, client, test_user):
        aid = self._create_analysis(client, test_user["token"])
        res = client.post(
            f"/api/v1/chat/{aid}/send",
            json={"content": "add a cache layer"},
            headers=auth_header(test_user["token"]),
        )
        data = res.json()
        assert data["modification_applied"] is True
        detail = client.get(f"/api/v1/analyze/{aid}", headers=auth_header(test_user["token"])).json()
        comps = detail["architecture_model"]["architecture"]["components"]
        assert any(c["type"] == "cache" for c in comps)

    def test_grounded_question(self, client, test_user):
        aid = self._create_analysis(client, test_user["token"])
        res = client.post(
            f"/api/v1/chat/{aid}/send",
            json={"content": "Explain the architecture pattern"},
            headers=auth_header(test_user["token"]),
        )
        assert res.status_code == 200
        assert res.json()["modification_applied"] is False
        assert res.json()["response"]


class TestValidationEndpoint:
    def test_validation_endpoint_after_modification(self, client, test_user, db_session):
        from backend.database import Analysis
        aid = client.post(
            "/api/v1/analyze",
            json={"business_problem": "Build a todo app"},
            headers=auth_header(test_user["token"]),
        ).json()["id"]
        client.post(
            f"/api/v1/chat/{aid}/send",
            json={"content": "add a cache layer"},
            headers=auth_header(test_user["token"]),
        )
        a = db_session.query(Analysis).filter(Analysis.id == aid).first()
        a.status = "completed"
        db_session.commit()
        res = client.get(f"/api/v1/analyze/{aid}/validation", headers=auth_header(test_user["token"]))
        assert res.status_code == 200
        data = res.json()
        assert "error_count" in data
        assert "warning_count" in data
        assert "passes" in data
