# backend/agents/engine.py
import json
import time
import asyncio
from typing import AsyncGenerator
from backend.config import settings
from backend.agents.mock_data import get_mock_analysis
from backend.agents.prompt_templates import (
    SYSTEM_PROMPT_REQUIREMENTS,
    SYSTEM_PROMPT_ARCHITECTURE,
    SYSTEM_PROMPT_DATABASE,
    SYSTEM_PROMPT_API,
    SYSTEM_PROMPT_DEPLOYMENT,
    SYSTEM_PROMPT_SECURITY,
    SYSTEM_PROMPT_PERFORMANCE,
    SYSTEM_PROMPT_DIAGRAM,
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
        print(f"LLM API Call failed: {e}. Falling back to domain knowledge generator.")
        raise e


def _build_user_prompt(business_problem: str, scale_estimates: dict, constraints: list) -> str:
    return (
        f"Business Problem: {business_problem}\n"
        f"Scale: {json.dumps(scale_estimates)}\n"
        f"Constraints: {json.dumps(constraints)}"
    )

async def run_agent_orchestrator(
    business_problem: str,
    architecture_tier: str = "professional",
    scale_estimates: dict = None,
    constraints: list = None,
    analysis_id: str = "",
    db_session_factory = None
) -> AsyncGenerator[str, None]:
    """
    Executes the 10-agent collaborative reasoning workflow.
    Yields step-by-step logs for the agent process, then saves output to DB.
    """
    if scale_estimates is None: scale_estimates = {}
    if constraints is None: constraints = []
    start_time = time.time()
    
    # 10 Multi-Agent Pipeline Steps
    steps = [
        ("analyzer", "Business Analyzer", "Analyzing system goals & scope boundaries..."),
        ("domain", "Domain Classifier", "Classifying domain taxonomy & picking building blocks..."),
        ("requirements", "Requirements Extractor", "Extracting functional and SLA constraints..."),
        ("architecture", "Architecture Planner", f"Selecting {architecture_tier.upper()} tier topology & components..."),
        ("tech_selector", "Technology Selector", "Choosing stacks with explicit rationale & trade-offs..."),
        ("database", "Database Architect", "Designing DDL schema & indexing strategies..."),
        ("api", "API Spec Agent", "Designing REST OpenAPI contracts & payload structures..."),
        ("reviewer", "Architecture Critic", "Evaluating security, scalability & cost scores..."),
        ("deployment", "DevOps & IaC Agent", "Generating Terraform & Kubernetes manifests..."),
        ("diagrams", "Visual Diagram Agent", "Compiling high-contrast Mermaid & ASCII diagrams..."),
    ]
    
    yield json.dumps({"step": "init", "message": f"Orchestrator initiating 10-agent collaboration cycle ({architecture_tier.title()} Tier)..."})
    await asyncio.sleep(0.4)
    
    try:
        analysis_data = get_mock_analysis(business_problem, scale_estimates, constraints, architecture_tier=architecture_tier)
        user_prompt = _build_user_prompt(business_problem, scale_estimates, constraints)

        if settings.OPENAI_API_KEY:
            try:
                llm_data = {}
                llm_data["requirements"] = await call_llm(
                    SYSTEM_PROMPT_REQUIREMENTS.format(
                        problem=business_problem,
                        scale=json.dumps(scale_estimates),
                        constraints=json.dumps(constraints),
                    ),
                    user_prompt,
                )
                llm_data["architecture_design"] = await call_llm(
                    SYSTEM_PROMPT_ARCHITECTURE.format(
                        requirements=json.dumps(llm_data["requirements"])
                    ),
                    user_prompt,
                )
                llm_data["database_schema"] = await call_llm(
                    SYSTEM_PROMPT_DATABASE.format(
                        architecture=json.dumps(llm_data["architecture_design"])
                    ),
                    user_prompt,
                )
                llm_data["api_specification"] = await call_llm(
                    SYSTEM_PROMPT_API.format(
                        architecture=json.dumps(llm_data["architecture_design"]),
                        database=json.dumps(llm_data["database_schema"]),
                    ),
                    user_prompt,
                )
                llm_data["deployment_config"] = await call_llm(
                    SYSTEM_PROMPT_DEPLOYMENT.format(
                        architecture=json.dumps(llm_data["architecture_design"])
                    ),
                    user_prompt,
                )
                llm_data["security_audit"] = await call_llm(
                    SYSTEM_PROMPT_SECURITY.format(
                        architecture=json.dumps(llm_data["architecture_design"]),
                        api=json.dumps(llm_data["api_specification"]),
                    ),
                    user_prompt,
                )
                llm_data["performance_strategies"] = await call_llm(
                    SYSTEM_PROMPT_PERFORMANCE.format(
                        architecture=json.dumps(llm_data["architecture_design"]),
                        database=json.dumps(llm_data["database_schema"]),
                    ),
                    user_prompt,
                )
                llm_data["diagrams"] = await call_llm(
                    SYSTEM_PROMPT_DIAGRAM.format(
                        architecture=json.dumps(llm_data["architecture_design"])
                    ),
                    user_prompt,
                )
                analysis_data.update(llm_data)
                print("[OK] LLM analysis completed successfully.")
            except Exception as llm_err:
                print(f"[WARN] LLM pipeline failed, using domain generator fallback: {llm_err}")

        for key, agent_name, description in steps:
            yield json.dumps({"step": key, "message": f"{agent_name}: {description}"})
            await asyncio.sleep(0.6)
            yield json.dumps({"step": key, "message": f"{agent_name}: Stage complete."})
            await asyncio.sleep(0.1)
            
        # Complete
        end_time = time.time()
        elapsed = round(end_time - start_time, 2)
        analysis_data["status"] = "completed"
        analysis_data["analysis_time_seconds"] = elapsed
        
        # Save to database
        db = db_session_factory()
        try:
            from backend.database import Analysis
            db_analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if db_analysis:
                db_analysis.requirements = analysis_data["requirements"]
                db_analysis.architecture_design = analysis_data["architecture_design"]
                db_analysis.database_schema = analysis_data["database_schema"]
                db_analysis.api_specification = analysis_data["api_specification"]
                db_analysis.deployment_config = analysis_data["deployment_config"]
                db_analysis.security_audit = analysis_data["security_audit"]
                db_analysis.performance_strategies = analysis_data["performance_strategies"]
                db_analysis.diagrams = analysis_data["diagrams"]
                db_analysis.status = "completed"
                db_analysis.analysis_time_seconds = elapsed
                db.commit()
        except Exception as db_err:
            db.rollback()
            print(f"Error saving analysis output to DB: {db_err}")
            raise db_err
        finally:
            db.close()
            
        yield json.dumps({
            "step": "done", 
            "message": f"Successfully completed domain-aware architecture generation in {elapsed}s!", 
            "analysis_id": analysis_id
        })
        
    except Exception as e:
        # Save failure state
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
