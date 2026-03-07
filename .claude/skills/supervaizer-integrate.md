# Supervaizer-integrate

Automate the integration of the Supervaizer Controller into any Python AI agent project. This skill analyzes the user's existing agent code, interactively gathers requirements, installs the supervaizer package, and generates fully customized controller files.

## When to use

Use this skill when the user wants to:
- Integrate the Supervaizer Controller into their Python AI agent
- Add Supervaize platform connectivity to an existing agent
- Set up A2A (Agent-to-Agent) protocol support for their agent
- Add human-in-the-loop workflows to their agent
- Make their agent discoverable and operable through the Supervaize platform

## Instructions

Follow these phases in order. Each phase must complete before moving to the next.

### Phase 1: Project Discovery & Analysis

1. **Scan the project structure** to understand:
   - Package manager: check for `pyproject.toml` (uv/poetry) vs `requirements.txt` (pip) vs `setup.py`
   - Web framework: check for FastAPI, Flask, Django, or no web framework
   - Existing agent code: look for Python files that implement AI agent logic (LangChain, CrewAI, AutoGen, OpenAI, Anthropic SDK, or custom)
   - Existing supervaizer integration: check if `supervaizer` is already installed or configured
   - Entry point: identify the main application file

2. **Analyze the agent's workflow** by reading the main agent files:
   - What does the agent do? (summarize its purpose)
   - What are its inputs? (API keys, user prompts, configuration)
   - What are its outputs? (generated content, decisions, reports)
   - What external services does it call? (LLMs, APIs, databases)
   - Does it have distinct processing stages or steps?

3. **Present findings** to the user with a summary like:
   ```
   Project Analysis:
   - Package manager: [uv/pip/poetry]
   - Framework: [FastAPI/Flask/none]
   - Agent type: [LangChain/CrewAI/custom/etc.]
   - Agent purpose: [brief description]
   - Detected inputs: [list]
   - Detected outputs: [list]
   - Detected stages: [list]
   ```

### Phase 2: Interactive Requirements Gathering

Ask the user the following questions using `AskUserQuestion`. Pre-fill suggested answers based on Phase 1 analysis.

**Question Set 1 - Agent Identity:**
- Agent name and description (suggest based on code analysis)
- Author name and email
- Version string
- Tags for discoverability

**Question Set 2 - Cases & Steps:**
- "What constitutes a single 'case' in your agent's workflow?" (suggest based on detected workflow units - e.g., "processing one document", "handling one customer request", "generating one report")
- "What are the distinct steps within each case?" (suggest based on detected processing stages - e.g., "1. Parse input, 2. Call LLM, 3. Format output")
- "Can your agent process multiple cases in a single job?" (yes/no, suggest based on whether the code has loops or batch processing)

**Question Set 3 - Data Reporting:**
- "What data should be reported to the Supervaize platform at each step?" For each detected step, ask what payload data matters. Common options:
  - Input data received
  - LLM tokens used / model called
  - Intermediate results
  - Final output / deliverable
  - Error details
  - Custom metrics
- "How should costs be calculated?" Options:
  - LLM API costs (auto-detect from litellm or provider SDK)
  - Fixed cost per case
  - Custom cost calculation
  - No cost tracking

**Question Set 4 - Human-in-the-Loop:**
- "Should any step require human approval before proceeding?" (suggest based on whether the agent makes consequential decisions)
- If yes: "At which step(s) should human approval be requested?"
- If yes: "What form fields should the human see?" (Approved/Rejected booleans, free text feedback, choice selection, etc.)
- If yes: "What information should be shown to the human for their decision?" (the case payload, a summary, specific fields)

**Question Set 5 - Parameters & Secrets:**
- "What API keys or secrets does your agent need?" (auto-detect from code: OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
- "What other configuration parameters should be settable from the Supervaize UI?" (auto-detect from env var usage)

**Question Set 6 - Job Input Fields:**
- "What inputs should the user provide when starting a job?" (detect from the agent's main function parameters or CLI arguments)
- For each field: name, type (CharField, IntegerField, BooleanField, ChoiceField, etc.), required (yes/no), description

### Phase 3: Install Supervaizer Package

1. **Detect the package manager** and install accordingly:

   For `pyproject.toml` (uv):
   ```bash
   # Add supervaizer to dependencies if not present
   # Then run: uv sync
   ```

   For `requirements.txt` (pip):
   ```bash
   # Add supervaizer>=0.10.23 to requirements.txt
   # Then run: pip install -r requirements.txt
   ```

   For `pyproject.toml` (poetry):
   ```bash
   poetry add supervaizer
   ```

2. **Also ensure these dependencies** are present (add if missing):
   - `fastapi>=0.128.0`
   - `loguru>=0.7.3`
   - `shortuuid` (for agent ID generation)

### Phase 4: Generate Controller Files

Generate the following files, customized based on the user's answers:

#### 4a. `supervaizer_control.py` - Main Controller Configuration

This is the central hub. Generate it with:
- Parameter definitions from Question Set 5
- Agent method definitions pointing to the agent implementation file
- Method fields from Question Set 6
- Agent declaration with metadata from Question Set 1
- Account setup with environment variable references
- Server configuration with A2A endpoints enabled

Use this structure:
```python
import os
import shortuuid
from supervaizer import (
    Agent,
    AgentMethods,
    Server,
    Account,
    AgentMethod,
    AgentMethodField,
    ParametersSetup,
    Parameter,
)

# === PARAMETERS ===
# Secrets and environment variables the agent needs
agent_parameters = ParametersSetup.from_list([
    # Generated from Question Set 5
    Parameter(name="...", description="...", is_environment=True, is_secret=True/False),
])

# === METHODS ===
# job_start: the main entry point for job execution
job_start_method = AgentMethod(
    name="start",
    method="agent_impl.job_start",  # Points to the implementation file
    is_async=False,
    params={"action": "start"},
    fields=[
        # Generated from Question Set 6
        AgentMethodField(name="...", type=..., field_type="...", required=True/False),
    ],
)

job_stop_method = AgentMethod(
    name="stop",
    method="agent_impl.job_stop",
    is_async=False,
    params={"action": "stop"},
    description="Stop the running job",
)

job_status_method = AgentMethod(
    name="status",
    method="agent_impl.job_status",
    is_async=False,
    params={"action": "status"},
    description="Get the status of the agent",
)

# If HITL is enabled, add human_answer method
# human_answer_method = AgentMethod(...)

# === AGENT ===
agent_name = "..."  # From Question Set 1
agent = Agent(
    name=agent_name,
    id=shortuuid.uuid(agent_name),
    author="...",
    version="...",
    description="...",
    tags=[...],
    methods=AgentMethods(
        job_start=job_start_method,
        job_stop=job_stop_method,
        job_status=job_status_method,
        # human_answer=human_answer_method,  # If HITL enabled
    ),
    parameters_setup=agent_parameters,
)

# === ACCOUNT ===
supervaize_account = Account(
    workspace_id=os.getenv("SUPERVAIZE_WORKSPACE_ID") or "dummy_workspace_id",
    api_key=os.getenv("SUPERVAIZE_API_KEY") or "dummy_api_key",
    api_url=os.getenv("SUPERVAIZE_API_URL") or "https://app.supervaize.com",
)

# === SERVER ===
sv_server = Server(
    agents=[agent],
    a2a_endpoints=True,
    supervisor_account=supervaize_account,
)

app = sv_server.app

if __name__ == "__main__":
    sv_server.launch(log_level="DEBUG")
```

#### 4b. `agent_impl.py` - Agent Implementation (Job/Case/Step Logic)

Generate this file wrapping the user's existing agent logic into the Supervaizer lifecycle pattern:

```python
from loguru import logger as log
from supervaizer import (
    Case,
    CaseNodeUpdate,
    EntityStatus,
    JobContext,
    JobInstructions,
    JobResponse,
)

# Import the shared account object
from __init__ import supervaize_account

# Import the user's existing agent logic
# from existing_agent_module import existing_function


def process_case(case_id: str, job_id: str, **kwargs) -> Case:
    """Process a single case through all steps."""

    # Step 1: Start the case
    case = Case.start(
        job_id=job_id,
        account=supervaize_account,
        name=f"Case {case_id}",
        description=f"...",  # From Question Set 2
    )

    # Step 2..N: Execute each step, reporting data at each one
    # For each step identified in Question Set 2:
    case.update(CaseNodeUpdate(
        name="Step Name",  # From Question Set 2
        cost=0.0,          # From Question Set 3 (cost tracking)
        payload={...},     # From Question Set 3 (data reporting)
        is_final=False,
    ))

    # If HITL is needed at this step (from Question Set 4):
    # case.request_human_input(
    #     CaseNodeUpdate(
    #         name="Human Review",
    #         cost=0.0,
    #         payload={
    #             "supervaizer_form": {
    #                 "question": "...",
    #                 "answer": {"fields": [...]},
    #             },
    #         },
    #         is_final=False,
    #     ),
    #     "Please review and approve.",
    # )
    # return case  # Case will be resumed by handle_human_input

    # Final step: close the case
    case.close(case_result={...})  # Final deliverable
    return case


def job_start(**kwargs) -> JobResponse | None:
    """Main job execution entry point."""
    log.info(f"Agent: Received kwargs: {kwargs}")

    job_fields = kwargs.get("fields", {})
    job_context: JobContext = kwargs.get("context", {})
    job_instructions: JobInstructions | None = job_context.job_instructions
    job_id = job_context.job_id

    cases = 0
    cost = 0.0

    # Extract job fields (from Question Set 6)
    # field_value = job_fields.get("Field Name")

    # Process cases (from Question Set 2)
    # The loop structure depends on whether the agent processes multiple cases
    for i in range(num_cases):
        # Check job instructions (max_cases, max_cost, stop_on_error)
        check, explanation = (
            job_instructions.check(cases=cases, cost=cost)
            if job_instructions
            else (True, "No conditions")
        )
        if not check:
            log.warning(f"Agent: STOPPING JOB: {explanation}")
            break

        case_id = f"C{i + 1}"
        try:
            case_result = process_case(case_id=case_id, job_id=job_id, **kwargs)
            cost += getattr(case_result, "cost", 0.0)
            cases += 1
        except Exception as e:
            log.error(f"Agent: Error on case {case_id}: {e}")
            if job_instructions and job_instructions.stop_on_error:
                raise

    return JobResponse(
        job_id=job_id,
        status=EntityStatus.COMPLETED,
        message="Job Completed",
        payload={...},  # Final deliverable from Question Set 3
        cost=cost,
    )


# If HITL is enabled (from Question Set 4):
# def handle_human_input(**kwargs) -> JobResponse:
#     """Called when a human submits their decision."""
#     context_raw = kwargs.get("context")
#     if isinstance(context_raw, dict):
#         job_context = JobContext(**context_raw)
#     else:
#         job_context = context_raw
#     job_id = job_context.job_id
#     fields = kwargs.get("fields", {})
#     payload = kwargs.get("payload") or {}
#     case_id = (
#         getattr(job_context, "case_id", None)
#         or fields.get("case_id")
#         or payload.get("case_id")
#     )
#     case = Case.resume(id=case_id, job_id=job_id, account=supervaize_account)
#     # Process human decision based on form fields
#     approved = fields.get("Approved") is True
#     if approved:
#         case.close(case_result={"status": "approved"})
#     else:
#         case.close(case_result={"status": "rejected"})
#     return JobResponse(
#         job_id=job_id,
#         status=EntityStatus.COMPLETED,
#         message="Human input processed",
#         payload={"case_id": case_id, "approved": approved},
#     )


def job_stop(**kwargs) -> None:
    """Called when the platform requests to stop the running job."""
    job_context = kwargs.get("context") or {}
    job_id = getattr(job_context, "job_id", None) or (
        job_context.get("job_id") if isinstance(job_context, dict) else None
    )
    log.info(f"Agent: job_stop requested for job_id={job_id}")


def job_status(**kwargs):
    """Return current agent status."""
    job_context = kwargs.get("context") or {}
    job_id = getattr(job_context, "job_id", None) or (
        job_context.get("job_id") if isinstance(job_context, dict) else None
    )
    log.info(f"Agent: job_status requested for job_id={job_id}")
    return {"status": "idle", "job_id": job_id}
```

#### 4c. `__init__.py` - Shared Account Export

If not already present:
```python
from supervaizer_control import supervaize_account
```

#### 4d. `.envrc_template` - Environment Variables

Generate with all required environment variables:
```bash
export SUPERVAIZE_API_URL=https://app.supervaize.com
export SUPERVAIZE_API_KEY=GET_FROM_APP.SUPERVAIZE.COM
export SUPERVAIZE_WORKSPACE_ID=your_workspace_slug
export SUPERVAIZER_HOST=localhost
export SUPERVAIZER_PORT=8000
export SUPERVAIZER_SCHEME=http
export SUPERVAIZER_PUBLIC_URL=http://localhost:8000
export SUPERVAIZER_SERVER_ID=TBD
export SUPERVAIZER_PRIVATE_KEY=TBD
# Agent-specific secrets (from Question Set 5)
# export OPENAI_API_KEY=...
```

#### 4e. `main.py` - Entry Point

If not already present or needs updating:
```python
from supervaizer_control import app, sv_server

__all__ = ["app"]

# Add any custom endpoints here
```

### Phase 5: Validation & Next Steps

1. **Verify the generated files** compile correctly:
   ```bash
   python -c "import supervaizer_control"
   ```

2. **Present a summary** to the user:
   ```
   Supervaizer Controller Integration Complete!

   Files created/modified:
   - supervaizer_control.py (controller configuration)
   - agent_impl.py (job/case/step implementation)
   - __init__.py (shared exports)
   - .envrc_template (environment variables)
   - main.py (entry point)
   - pyproject.toml / requirements.txt (dependencies updated)

   Next steps:
   1. Create your developer account at https://app.supervaize.com
   2. Generate an API key and get your workspace ID
   3. Fill in the environment variables in .envrc_template
   4. Run: supervaizer start (or python supervaizer_control.py)
   5. Verify at http://localhost:8000/docs
   6. For production: supervaizer deploy up
   ```

3. **Offer to help** with:
   - Customizing the case processing logic further
   - Adding additional agents
   - Setting up deployment (Vercel, GCP, AWS, DigitalOcean)
   - Adding more human-in-the-loop steps

## Key Supervaizer Concepts Reference

### Entity Hierarchy
- **Server** -> hosts multiple **Agents**
- **Agent** -> receives **Jobs** (from the Supervaize platform)
- **Job** -> contains multiple **Cases** (units of work)
- **Case** -> has **Steps** (CaseNodeUpdate) that are either informational or human-in-the-loop

### Required Agent Methods
- `job_start(**kwargs)` -> `JobResponse` - Main execution entry point
- `job_stop(**kwargs)` -> `None` - Graceful stop handler
- `job_status(**kwargs)` -> `dict` - Status reporting

### Optional Agent Methods
- `human_answer(**kwargs)` -> `JobResponse` - Process human decisions
- `chat(**kwargs)` - Chat-style interaction
- `custom` methods - Any additional custom methods

### Job kwargs Structure
```python
kwargs = {
    "fields": {...},           # User-provided job input fields
    "context": JobContext,      # job_id, mission_id, workspace info, job_instructions
    "conditions": JobInstructions,  # max_cost, max_cases, stop_on_error, etc.
}
```

### CaseNodeUpdate (Step) Fields
```python
CaseNodeUpdate(
    name="Step Name",          # Human-readable step name
    cost=0.0,                  # Cost incurred at this step
    payload={...},             # Data to report to the platform
    is_final=False,            # True if this is the last step
    error=None,                # Error message if step failed
)
```

### Human-in-the-Loop Form Fields
```python
{
    "supervaizer_form": {
        "question": "Review and approve this case",
        "answer": {
            "fields": [
                {"name": "Approved", "type": bool, "field_type": "BooleanField", "required": False},
                {"name": "Feedback", "type": str, "field_type": "CharField", "required": False},
            ]
        }
    }
}
```

### AgentMethodField Types
- `CharField` - Text input
- `IntegerField` - Integer input
- `BooleanField` - True/False toggle
- `ChoiceField` - Single selection dropdown
- `MultipleChoiceField` - Multi-select
- `JSONField` - Raw JSON input
