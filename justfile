# Justfile
set dotenv-load := true
set dotenv-filename := ".env"

default:
    @just --list

# ─────────────────────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────────────────────

# Install dependencies
install:
    uv sync

# Install dev dependencies
install-dev:
    uv sync --dev

# After install-dev: use editable supervaizer from monorepo checkout (not for CI; path is relative to supervaize_hello_world/)
use-local-supervaizer:
    uv pip install -e ../supervaizer

# Dev deps + local editable supervaizer
install-dev-local:
    uv sync --dev
    just use-local-supervaizer

# ─────────────────────────────────────────────────────────────────────────────
# Server
# ─────────────────────────────────────────────────────────────────────────────

start:
    #!/usr/bin/env bash
    set -euo pipefail
    supervaizer start --port 3000 --local

# Needs SUPERVAIZE_API_URL / SUPERVAIZE_API_KEY / SUPERVAIZE_WORKSPACE_ID in the env.
# A Studio running in Docker on this machine calls back through host.docker.internal.
# Set SUPERVAIZER_SERVER_ID to the id Studio already knows, or each run registers a new server and agent.
# SUPERVAIZER_WORKSPACE_AUTH_ISSUER is the Studio SPA origin (the Developer page shows it).
# Run with Studio registration (`just start` is local mode: it never registers)
start-studio port="8001":
    #!/usr/bin/env bash
    set -euo pipefail
    export SUPERVAIZER_LOCAL_MODE=false
    export SUPERVAIZER_WORKSPACE_AUTH_REQUIRED=true
    export SUPERVAIZER_WORKSPACE_AUTH_ISSUER="${SUPERVAIZER_WORKSPACE_AUTH_ISSUER:-https://studio.supervaize.com}"
    export SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL="${SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL:-${SUPERVAIZE_API_URL%/}/api/v1/teams/${SUPERVAIZE_WORKSPACE_ID}/workspace-agent-grants/jwks/}"
    uv run supervaizer start --port {{port}} --public-url "http://host.docker.internal:{{port}}"

# ─────────────────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────────────────

# Run all tests
test:
    uv run pytest tests/ -v

# Run a specific test
test-one test_name:
    uv run pytest tests/ -k "{{test_name}}" -v

# ─────────────────────────────────────────────────────────────────────────────
# Vercel
# ─────────────────────────────────────────────────────────────────────────────

# Send the environment variables to Vercel
vercel_add_env:
    printf '%s' "$SUPERVAIZE_API_URL" | vercel env add SUPERVAIZE_API_URL production --force
    printf '%s' "$SUPERVAIZE_API_KEY" | vercel env add SUPERVAIZE_API_KEY production --sensitive --force
    printf '%s' "$SUPERVAIZE_WORKSPACE_ID" | vercel env add SUPERVAIZE_WORKSPACE_ID production --force
    printf '%s' "$SUPERVAIZER_HOST" | vercel env add SUPERVAIZER_HOST production --force
    printf '%s' "$SUPERVAIZER_PORT" | vercel env add SUPERVAIZER_PORT production --force
    printf '%s' "$SUPERVAIZER_SCHEME" | vercel env add SUPERVAIZER_SCHEME production --force
    printf '%s' "$SUPERVAIZE_PUBLIC_URL" | vercel env add SUPERVAIZE_PUBLIC_URL production --force

# Tag v<version> on origin/main, push the tag, then deploy to Vercel production
deploy:
    #!/usr/bin/env bash
    set -euo pipefail
    version="$(uv version --short)"
    git fetch -q origin
    # The deployed tree must be exactly origin/main, so the tag points at what is live.
    git diff --quiet origin/main || { echo "Working tree differs from origin/main: merge the PR and run 'but pull' first"; exit 1; }
    grep -q "AGENT_VERSION = \"$version\"" supervaizer_control.py || { echo "AGENT_VERSION in supervaizer_control.py is not $version"; exit 1; }
    git tag -a "v$version" -m "v$version" origin/main
    git push origin "v$version"
    vercel --prod

# Redeploy the current version without a new tag
vercel_redeploy:
    vercel --prod

# Test locally with Vercel
vercel_dev:
    vercel dev
