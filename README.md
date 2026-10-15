# Supervaize Hello World

A minimal example demonstrating how to build and deploy agents with **Supervaize** using the **Supervaizer Controller**.

## What This Example Demonstrates

This project showcases all core Supervaizer concepts:

- **Agent Parameters** — Defining environment variables and secrets
- **Agent Methods** — Implementing `start`, `stop`, and `status` handlers
- **Server Configuration** — A2A protocol support and admin interface
- **Cloud Deployment** — One-click Vercel deployment

## Project Structure

```
supervaize_hello_world/
├── supervaizer_control.py   # Main controller configuration
├── agent_v2.py              # Supervaizer v2 registration (SDK builder) and A2UI handlers
├── agent_configurator.py    # Job Configurator A2UI surface example
├── agent_simple.py          # Agent logic (job_start, job_stop, job_status)
├── pyproject.toml           # Project dependencies
├── .envrc_template          # Environment variables template
└── README.md
```

## Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip
- An account at [supervaize](app.supervaize.com)

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/supervaize/supervaize_hello_world.git
cd supervaize_hello_world
```

### 2. Set up the environment

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Start the server

```bash
supervaizer start
```

Your agent will be available at `http://localhost:8000`.

`supervaizer start --local` (what `just start` runs) never registers with Studio. To register the agent with a Studio, load the Studio env (`SUPERVAIZE_API_URL`, `SUPERVAIZE_API_KEY`, `SUPERVAIZE_WORKSPACE_ID`) and run:

```bash
just start-studio
```

It listens on port 8001 and registers `http://host.docker.internal:8001`, which a Studio running in Docker on this machine can call back. Set `SUPERVAIZER_SERVER_ID` to the server id Studio already knows for this agent; otherwise each run registers a new server and a new agent.
Workspace authorization is required for a Studio-registered controller: the recipe derives the JWKS URL from the Studio env and uses `https://studio.supervaize.com` as the issuer. Set `SUPERVAIZER_WORKSPACE_AUTH_ISSUER` to your Studio's SPA origin (shown on its Developer page) when it is not production.

## Available Endpoints

Once running, you can access:

| Endpoint | Description |
|----------|-------------|
| `http://localhost:8000/docs` | API Documentation (Swagger) |
| `http://localhost:8000/redoc` | API Documentation (ReDoc) |
| `http://localhost:8000/admin` | Admin Interface |
| `http://localhost:8000/.well-known/agents.json` | A2A Agent Discovery |
| `http://localhost:8000/.well-known/health` | Health Check |

## Data Resources

The `simple_agent` now exposes a **Contacts** data resource via the Supervaizer SDK. Studio renders it as a generic CRUD table — no per-agent UI code required.

The in-memory contacts store (`agent_data_resource.py`) demonstrates the full DataResource pattern:
- `on_list` / `on_get` — read operations
- `on_create` / `on_update` / `on_delete` — write operations
- `on_import` — bulk CSV import (enabled via `importable=True`)

Run E2E tests with:
```bash
just test
```

## Shared Dashboard and Metrics

The simple agent declares the `mission.analytics` surface and a mission-scoped dataset `hello_cases` (`agent_dashboard.py`). Studio shows an **Analytics** link on the mission page, loads the `Dashboard` document (one dataset with three KPI metrics: cases, distinct cities and completed ratio; a status filter; a Vega-Lite bar chart of cases by city; a table), then queries `dataset.hello_cases.query` and renders the rows. The rows come from the jobs this controller started, so on a serverless host they only cover the warm instance.

## Configure Form

The Job Configurator (`job.configurator` surface, `agent_configurator.py`) is the per-job configure form: greeting (text), signature (text) and shout (boolean). Saves go through `job.configure` with the revision they were made from, and the values shape the case messages of the next start.

## Human in the Loop

The simple agent's start form has an **Add human in the loop** switch. Each start creates `count` completed cases with random content (a name, a city and a greeting message in the case metadata; the greeting comes from the Job Configurator). With the switch on, one more case waits on a human approval step: Studio renders the `case.step.awaiting` surface and the agent completes the case on `step.awaiting.submit`. See `tests/test_hitl.py`.

## Rule checkpoints

The simple agent declares `capabilities.rule_checkpoints` (version 1, phases `before` and `after`) in `agent_v2.py`. The SDK then also declares the `rule.checkpoint.resume` action (job scope). Studio requires both before it starts a job in a mission with rules (`studio/apps/guardrails/services/admission.py`).

`agent_rules.py` runs the flow with the SDK's `RuleCheckpointGate`:

1. `job.start` arrives with an opaque `rule_snapshot` in its input. The agent keeps the gate in memory and returns the hello steps as `pending`. Studio knows a v2 case only once a job state has projected it, so no checkpoint is posted yet.
2. `job.sync` posts a `before` and an `after` checkpoint per "Say hello" step to `{api_url}/api/v1/rule-checkpoints/`, with the greeting as business context. An `allow` completes the step. A `stop` fails the step and the job.
3. A `pause` parks the step as `awaiting` with reason `rule_checkpoint` and action `rule.checkpoint.resume`. The decision is taken in Studio's guardrails UI, not through the step surface.
4. Studio pushes the decision with `rule.checkpoint.resume`. The SDK's `resume_rule_checkpoint` matches it to the live gate, then the agent finishes the step and runs the remaining checkpoints. Studio sees the result on its next `job.sync`.

Jobs started without rules behave as before. The gate lives in process memory: after a restart (a Vercel cold start) the agent answers a decision with `rule.checkpoint.rejected`. A real agent persists the snapshot with its job. See `tests/test_rule_checkpoints.py`.

## Scheduled Starts

The `simple_agent` advertises `capabilities.scheduled_start: true` in its v2 registration (`agent_v2.py`). With that flag a Studio mission manager can start the agent on a cron schedule (Studio job scheduling, PR #917).

The agent does not run a clock or parse cron. Studio owns the schedule and calls the normal `job.start` action when a firing is due, with:

- a stable `idempotency_key` per occurrence. The agent returns the original job on a retry instead of starting a second one (`_started_jobs` in `agent_v2.py`).
- a top-level `schedule` object (`schedule_id`, `schedule_name`, `run_id`, `run_number`, `occurrence_at`, `trigger`, `cron_expression`, `timezone`, `error_policy`). The agent only names it in its result message.

See `tests/test_scheduling.py` and the SDK contract in `supervaizer/docs/2026_10_SCHEDULED_START.md`.

## Job Configurator

The `simple_agent` also declares the `job.configurator` surface (`agent_configurator.py`). Studio renders it on the job page as an A2UI `Configurator` document: one editable section with a greeting field. Saving invokes the bound `job.configure` action with `{"revision": ..., "value": {"greeting": ...}}`. A save made from a stale revision gets `configurator.conflict` back and Studio reloads the document. The saved greeting names the job's cases.

## Testing the Agent

The E2E tests play Studio: `tests/conftest.py` installs a throwaway Ed25519 key on the server and signs a workspace token per agent, because Supervaizer 1.x fail-closes A2A and data-resource calls without one.

```bash
# Check agent health
curl http://localhost:8000/.well-known/health

# View agent card (A2A discovery)
curl http://localhost:8000/.well-known/agents.json
```

## Configuration

### Environment Variables

Copy `.envrc_template` to `.envrc` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPERVAIZE_API_KEY` | No* | API key for Supervaize platform |
| `SUPERVAIZE_WORKSPACE_ID` | No* | Your workspace ID |
| `SUPERVAIZE_API_URL` | No* | Supervaize API URL |
| `SUPERVAIZER_HOST` | No | Server host (default: 0.0.0.0) |
| `SUPERVAIZER_PORT` | No | Server port (default: 8000) |
| `SUPERVAIZER_PUBLIC_URL` | No | Public URL for callbacks |

*Required only when connecting to the Supervaize platform.

### Agent Configuration

Edit `supervaizer_control.py` to customize:

- Agent metadata (name, description, tags)
- Parameters and secrets
- Agent methods and their handlers

## Cloud Deployment

### Deploy with Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Falain-sv%2Fsupervaize_hello_world)

1. Click the deploy button above
2. Add environment variables from `.envrc_template` in Vercel Project Settings
3. Deploy!

Or deploy via CLI:

```bash
npm i -g vercel
vercel
```

### Release a new version

1. Set the version in `pyproject.toml` (`uv version 1.3`) and `AGENT_VERSION` in `supervaizer_control.py`.
2. Merge the change into `main` and run `but pull`.
3. Run `just deploy`: it tags `v<version>` on `origin/main`, pushes the tag, then runs `vercel --prod`.

`just vercel_redeploy` redeploys the current version without a new tag.

For more information, see the [Vercel Python Runtime documentation](https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python).

## Troubleshooting

### Port already in use

Change the port in your environment or edit `supervaizer_control.py`:

```bash
export SUPERVAIZER_PORT=8001
supervaizer start
```

### Module not found

Ensure you've installed the package in editable mode:

```bash
uv pip install -e .
```

## Documentation

For comprehensive documentation, visit:

- [Quickstart Guide](https://doc.supervaize.com/docs/supervaizer-controller/quickstart)
- [Controller Setup Guide](https://doc.supervaize.com/docs/supervaizer-controller/controller-setup)
- [Cloud Deployment](https://doc.supervaize.com/docs/supervaizer-controller/deploy)
- [A2A Protocol Support](https://doc.supervaize.com/docs/supervaizer-controller/ref/PROTOCOLS)

## License

This project is licensed under the [Mozilla Public License 2.0](LICENSE).
