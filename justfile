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
