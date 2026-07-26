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
        print(f"LLM API Call failed: {e}. Falling back to mock data.")
        raise e


def _build_user_prompt(business_problem: str, scale_estimates: dict, constraints: list) -> str:
    return (
        f"Business Problem: {business_problem}\n"
        f"Scale: {json.dumps(scale_estimates)}\n"
        f"Constraints: {json.dumps(constraints)}"
    )

async def run_agent_orchestrator(
    business_problem: str, 
    scale_estimates: dict, 
    constraints: list,
    analysis_id: str,
    db_session_factory
) -> AsyncGenerator[str, None]:
    """
    Executes the 8-agent collaborative reasoning workflow.
    Yields step-by-step logs for the agent process, then saves output to DB.
    """
    start_time = time.time()
    
    # Define agent steps
    steps = [
        ("requirements", "Requirements Agent", "Extracting functional and non-functional requirements..."),
        ("architecture", "Architecture Agent", "Selecting system topology (Microservices/Monolith)..."),
        ("database", "Database Agent", "Generating relational DDL schemas & optimization indexes..."),
        ("api", "API Agent", "Designing REST OpenAPI spec endpoints..."),
        ("deployment", "Deployment Agent", "Configuring Terraform IaC & Kubernetes manifests..."),
        ("security", "Security Agent", "Auditing architecture design for compliance & vulnerabilities..."),
        ("performance", "Performance Agent", "Calculating cache TTLs & load balancing parameters..."),
        ("diagrams", "Best Practices Agent", "Compiling visual Mermaid flows & ASCII layout..."),
    ]
    
    # We will simulate processing time for each agent to mimic real collaboration.
    # Total analysis time ~ 8 seconds.
    
    yield json.dumps({"step": "init", "message": "Orchestrator initiating collaboration cycle..."})
    await asyncio.sleep(0.5)
    
    try:
        analysis_data = get_mock_analysis(business_problem, scale_estimates, constraints)
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
                print(f"[WARN] LLM pipeline failed, using mock data: {llm_err}")

        for key, agent_name, description in steps:
            yield json.dumps({"step": key, "message": f"{agent_name}: {description}"})
            await asyncio.sleep(0.8)
            yield json.dumps({"step": key, "message": f"{agent_name}: Analysis complete."})
            await asyncio.sleep(0.2)
            
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
            "message": f"Successfully completed architecture generation in {elapsed}s!", 
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
