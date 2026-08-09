# backend/agents/engine.py
import json
import time
import asyncio
from typing import AsyncGenerator

from backend.config import settings
from backend.agents.mock_data import get_mock_analysis
from backend.agents.model import (
    new_model,
    ensure_dict,
    ensure_list,
    as_text,
    normalize_component,
    normalize_decision,
    normalize_ambiguity,
    normalize_relationship,
    normalize_recommendation,
    validate_model,
    to_legacy_fields,
)
from backend.agents.prompt_templates import (
    PIPELINE_STEPS,
    build_stage_prompt,
)


async def call_llm(system_prompt: str, user_prompt: str) -> dict:
    if not settings.OPENAI_API_KEY:
        raise ValueError("No API Key configured")

    try:
        import openai
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"LLM API Call failed: {e}.")
        raise e


# ---------------------------------------------------------------------------
# Per-stage merge: LLM JSON -> canonical model section
# ---------------------------------------------------------------------------

def _merge_stage(model: dict, key: str, data: dict) -> None:
    """Merge one stage's JSON output into the canonical model."""
    data = ensure_dict(data)

    if key == "analyzer":
        scale = ensure_dict(data.get("scale"))
        workload = model["performance"]["workload"]
        for field in ("avg_requests_per_second", "peak_requests_per_second",
                      "expected_concurrency", "users"):
            val = scale.get(field)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                workload[field] = val
        if scale.get("calculated_from"):
            workload["calculated_from"] = as_text(scale.get("calculated_from"))
        for a in ensure_list(scale.get("assumptions")):
            model["requirements"]["assumptions"].append(a)
        model["requirements"]["actors"] = ensure_list(data.get("actors")) or model["requirements"]["actors"]
        for a in ensure_list(data.get("ambiguities")):
            model["requirements"]["ambiguities"].append(normalize_ambiguity(a))
        model["requirements"]["constraints"] = ensure_list(data.get("constraints")) or model["requirements"]["constraints"]
        model["scale_estimates"]["system_name"] = as_text(data.get("system_name"))
        model["scale_estimates"]["summary"] = as_text(data.get("summary"))

    elif key == "domain":
        model["domain"] = as_text(data.get("domain")) or model["domain"]
        cs = data.get("complexity_score")
        if isinstance(cs, (int, float)) and not isinstance(cs, bool):
            model["performance"]["workload"]["complexity_score"] = cs
        model["architecture"]["building_blocks"] = ensure_list(data.get("building_blocks"))

    elif key == "requirements":
        reqs = model["requirements"]
        reqs["functional"] = ensure_list(data.get("functional"))
        reqs["non_functional"] = ensure_list(data.get("non_functional"))
        reqs["constraints"] = ensure_list(data.get("constraints"))
        for a in ensure_list(data.get("assumptions")):
            reqs["assumptions"].append(a)
        for a in ensure_list(data.get("ambiguities")):
            reqs["ambiguities"].append(normalize_ambiguity(a))
        reqs["business_rules"] = ensure_list(data.get("business_rules"))

    elif key == "architecture":
        arch = model["architecture"]
        arch["system_type"] = as_text(data.get("system_type"))
        arch["pattern"] = as_text(data.get("pattern"))
        arch["justification"] = as_text(data.get("justification"))
        arch["components"] = [
            normalize_component(c, i) for i, c in enumerate(ensure_list(data.get("components")))
        ]
        arch["relationships"] = [
            normalize_relationship(r, i) for i, r in enumerate(ensure_list(data.get("relationships")))
        ]
        arch["decisions"] = [
            normalize_decision(d, i) for i, d in enumerate(ensure_list(data.get("decisions")))
        ]

    elif key == "tech_selector":
        arch = model["architecture"]
        arch["technologies"] = ensure_list(data.get("technologies"))
        for d in ensure_list(data.get("decisions")):
            arch["decisions"].append(normalize_decision(d, len(arch["decisions"])))

    elif key == "database":
        db = model["database"]
        db["database_type"] = as_text(data.get("database_type"))
        db["justification"] = as_text(data.get("justification"))
        db["schemas"] = ensure_list(data.get("schemas"))
        db["indexing_strategies"] = ensure_list(data.get("indexing_strategies"))
        db["transactions"] = as_text(data.get("transactions"))
        db["sharding"] = as_text(data.get("sharding"))
        db["migrations"] = as_text(data.get("migrations"))
        db["caching_layer"] = as_text(data.get("caching_layer"))

    elif key == "api":
        api = model["api"]
        api["protocol"] = as_text(data.get("protocol")) or api["protocol"]
        api["authentication_strategy"] = as_text(data.get("authentication_strategy"))
        api["endpoints"] = ensure_list(data.get("endpoints"))
        api["rate_limits"] = as_text(data.get("rate_limits"))
        api["versioning"] = as_text(data.get("versioning"))
        api["error_handling"] = as_text(data.get("error_handling"))
        api["idempotency"] = as_text(data.get("idempotency"))

    elif key == "deployment":
        dep = model["deployment"]
        dep["provider"] = as_text(data.get("provider"))
        dep["regions"] = ensure_list(data.get("regions"))
        dep["orchestration"] = as_text(data.get("orchestration"))
        dep["terraform_sample"] = as_text(data.get("terraform_sample"))
        dep["kubernetes_manifest"] = as_text(data.get("kubernetes_manifest"))
        dep["scaling_policy"] = as_text(data.get("scaling_policy"))
        dep["disaster_recovery"] = as_text(data.get("disaster_recovery"))
        dep["ci_cd"] = as_text(data.get("ci_cd"))

    elif key == "security":
        sec = model["security"]
        sec["authentication_strategy"] = as_text(data.get("authentication_strategy"))
        sec["authorization"] = as_text(data.get("authorization"))
        sec["data_protection"] = as_text(data.get("data_protection"))
        sec["vulnerability_mitigations"] = ensure_list(data.get("vulnerability_mitigations"))
        sec["compliance"] = as_text(data.get("compliance"))
        sec["scores"] = ensure_dict(data.get("scores"))
        sec["threat_model"] = ensure_list(data.get("threat_model"))

    elif key == "performance":
        perf = model["performance"]
        perf["latency_targets"] = ensure_dict(data.get("latency_targets"))
        perf["database_pressure"] = as_text(data.get("database_pressure"))
        perf["bottlenecks"] = ensure_list(data.get("bottlenecks"))
        perf["cache_requirements"] = as_text(data.get("cache_requirements"))
        perf["queue_requirements"] = as_text(data.get("queue_requirements"))
        perf["scaling_requirements"] = as_text(data.get("scaling_requirements"))
        perf["recommendations"] = [
            normalize_recommendation(r, i)
            for i, r in enumerate(ensure_list(data.get("recommendations")))
        ]

    elif key == "reviewer":
        review = model["review"]
        review["overall_score"] = data.get("overall_score")
        review["categories"] = ensure_dict(data.get("categories"))
        review["critical_issues"] = ensure_list(data.get("critical_issues"))
        review["warnings"] = ensure_list(data.get("warnings"))
        review["recommendations"] = ensure_list(data.get("recommendations"))
        review["missing_information"] = ensure_list(data.get("missing_information"))

    elif key == "final":
        model["overview"] = as_text(data.get("overview"))
        modes = ensure_dict(data.get("explanation_modes"))
        em = model["architecture"]["explanation_modes"]
        em["story"] = as_text(modes.get("story"))
        em["brief"] = as_text(modes.get("brief"))
        em["long"] = as_text(modes.get("long"))
        em["detailed"] = as_text(modes.get("detailed"))
        em["terms"] = ensure_list(modes.get("terms"))
        em["analogies"] = ensure_list(modes.get("analogies"))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def run_agent_orchestrator(
    business_problem: str,
    architecture_tier: str = "professional",
    scale_estimates: dict = None,
    constraints: list = None,
    analysis_id: str = "",
    db_session_factory = None
) -> AsyncGenerator[str, None]:
    """
    Dependency-ordered multi-agent pipeline over ONE canonical model.
    Yields step-by-step logs, then persists the model (plus legacy fields) to DB.
    Falls back to the domain generator when no API key is configured or any
    stage fails. Self-corrects at most MAX_CORRECTION_ITERATIONS times.
    """
    if scale_estimates is None: scale_estimates = {}
    if constraints is None: constraints = []
    start_time = time.time()

    yield json.dumps({"step": "init",
                      "message": f"Orchestrator initiating dependency-ordered agent pipeline ({architecture_tier.title()} Tier)..."})
    await asyncio.sleep(0.4)

    try:
        model = get_mock_analysis(business_problem, scale_estimates, constraints,
                                  architecture_tier=architecture_tier)
        used_llm = False

        if settings.OPENAI_API_KEY:
            try:
                model = new_model(business_problem, domain="General",
                                  architecture_tier=architecture_tier,
                                  scale_estimates=scale_estimates)
                for key, agent_name, description, _builder in PIPELINE_STEPS:
                    system, user = build_stage_prompt(
                        key, model, business_problem, architecture_tier,
                        scale_estimates, constraints, validate_model(model),
                    )
                    yield json.dumps({"step": key, "message": f"{agent_name}: {description}"})
                    data = await call_llm(system, user)
                    _merge_stage(model, key, data)
                    yield json.dumps({"step": key, "message": f"{agent_name}: Stage complete."})
                    await asyncio.sleep(0.1)

                used_llm = True
                print("[OK] LLM pipeline completed successfully.")

                # --- Bounded self-correction driven by the reviewer ----------
                from backend.agents.mock_data import MAX_CORRECTION_ITERATIONS
                while (model.get("correction_iterations", 0) < MAX_CORRECTION_ITERATIONS
                       and model["review"].get("critical_issues")):
                    model["correction_iterations"] = int(model.get("correction_iterations", 0)) + 1
                    concerns = "\n".join(model["review"].get("critical_issues", []))
                    yield json.dumps({
                        "step": "correct",
                        "message": f"Reviewer demanded changes; correction round {model['correction_iterations']}.",
                    })
                    redo = ["architecture", "tech_selector", "database", "api",
                            "deployment", "security", "performance", "reviewer"]
                    for key in redo:
                        for stage_key, agent_name, _desc, _builder in PIPELINE_STEPS:
                            if stage_key == key:
                                system, user = build_stage_prompt(
                                    key, model, business_problem, architecture_tier,
                                    scale_estimates, constraints, validate_model(model),
                                )
                                user += f"\n\nAddress these reviewer concerns:\n{concerns}"
                                data = await call_llm(system, user)
                                _merge_stage(model, key, data)
                                break
                    model["review"]["critical_issues"] = ensure_list(model["review"].get("critical_issues"))

            except Exception as llm_err:
                print(f"[WARN] LLM pipeline failed, using domain generator fallback: {llm_err}")
                model = get_mock_analysis(business_problem, scale_estimates, constraints,
                                          architecture_tier=architecture_tier)
                used_llm = False

        # Diagrams are always regenerated from the model so they can never drift.
        if not used_llm:
            for key, agent_name, description, _builder in PIPELINE_STEPS:
                if key in ("reviewer", "final"):
                    continue
                yield json.dumps({"step": key, "message": f"{agent_name}: {description}"})
                await asyncio.sleep(0.4)
                yield json.dumps({"step": key, "message": f"{agent_name}: Stage complete."})
                await asyncio.sleep(0.05)

        # Diagrams, explanation modes and alternatives are always regenerated
        # from the final model so they can never drift from the canonical state.
        from backend.agents.mock_data import (
            build_diagrams, build_explanation_modes, build_alternatives,
            build_deep_overview,
        )
        model["diagrams"] = build_diagrams(model)
        model["architecture"]["explanation_modes"] = build_explanation_modes(model)
        model["architecture"]["alternatives"] = build_alternatives(model)
        model["overview_explained"] = build_deep_overview(model)

        # Re-validate the finished model.
        validation = validate_model(model)

        end_time = time.time()
        elapsed = round(end_time - start_time, 2)
        model["status"] = "completed"
        model["analysis_time_seconds"] = elapsed
        model["validation"] = {
            "issue_count": len(validation),
            "issues": validation,
        }

        # Save canonical model + legacy fields to DB.
        legacy = to_legacy_fields(model)
        db = db_session_factory()
        try:
            from backend.database import Analysis
            db_analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if db_analysis:
                db_analysis.requirements = legacy["requirements"]
                db_analysis.architecture_design = legacy["architecture_design"]
                db_analysis.database_schema = legacy["database_schema"]
                db_analysis.api_specification = legacy["api_specification"]
                db_analysis.deployment_config = legacy["deployment_config"]
                db_analysis.security_audit = legacy["security_audit"]
                db_analysis.performance_strategies = legacy["performance_strategies"]
                db_analysis.diagrams = legacy["diagrams"]
                db_analysis.architecture_model = model
                db_analysis.status = "completed"
                db_analysis.analysis_time_seconds = elapsed
                db.commit()
        except Exception as db_err:
            db.rollback()
            print(f"Error saving analysis output to DB: {db_err}")
            raise
        finally:
            db.close()

        yield json.dumps({
            "step": "done",
            "message": f"Successfully completed domain-aware architecture generation in {elapsed}s!",
            "analysis_id": analysis_id,
        })

    except Exception as e:
        db = db_session_factory()
        try:
            from backend.database import Analysis
            db_analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if db_analysis:
                db_analysis.status = "failed"
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        yield json.dumps({"step": "error", "message": f"Orchestrator encountered error: {str(e)}"})
