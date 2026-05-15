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
    echo $SUPERVAIZE_API_URL | vercel env add SUPERVAIZE_API_URL production --force
    echo $SUPERVAIZE_API_KEY | vercel env add SUPERVAIZE_API_KEY production --sensitive --force
    echo $SUPERVAIZE_WORKSPACE_ID | vercel env add SUPERVAIZE_WORKSPACE_ID production --force
    echo $SUPERVAIZER_HOST | vercel env add SUPERVAIZER_HOST production --force
    echo $SUPERVAIZER_PORT | vercel env add SUPERVAIZER_PORT production --force
    echo $SUPERVAIZER_SCHEME | vercel env add SUPERVAIZER_SCHEME production --force
    echo $SUPERVAIZE_PUBLIC_URL | vercel env add SUPERVAIZE_PUBLIC_URL production --force

vercel_redeploy:
    vercel --prod

# Test locally with Vercel
vercel_dev:
    vercel dev
