# Claude Code Project Configuration

## Skills

### Supervaizer-integrate
- **Trigger**: When user wants to integrate the Supervaizer Controller into a Python AI agent project
- **Command**: `/supervaizer-integrate`
- **Location**: `.claude/skills/supervaizer-integrate.md`
- **What it does**: Analyzes the user's existing Python agent code, interactively gathers requirements (cases, steps, data reporting, human-in-the-loop needs), installs the supervaizer package, and generates customized controller files.

## Project Context

This is a demonstration/reference project for the Supervaizer Controller framework. It shows how to build and deploy AI agents integrated with the Supervaize platform.

Key patterns:
- `supervaizer_control.py` - Central controller configuration (parameters, methods, agents, server)
- `agent_*.py` - Agent implementation files (job/case/step lifecycle)
- `main.py` - FastAPI entry point
- `.envrc_template` - Environment variable template

## Dependencies
- Python 3.12+
- Package manager: uv
- Key packages: supervaizer, fastapi, loguru
