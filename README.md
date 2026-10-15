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

## Scheduled Starts

The `simple_agent` advertises `capabilities.scheduled_start: true` in its v2 registration (`agent_v2.py`). With that flag a Studio mission manager can start the agent on a cron schedule (Studio job scheduling, PR #917).

The agent does not run a clock or parse cron. Studio owns the schedule and calls the normal `job.start` action when a firing is due, with:

- a stable `idempotency_key` per occurrence. The agent returns the original job on a retry instead of starting a second one (`_started_jobs` in `agent_v2.py`).
- a top-level `schedule` object (`schedule_id`, `schedule_name`, `run_id`, `run_number`, `occurrence_at`, `trigger`, `cron_expression`, `timezone`, `error_policy`). The agent only names it in its result message.

See `tests/test_scheduling.py` and the SDK contract in `supervaizer/docs/2026_10_SCHEDULED_START.md`.

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
