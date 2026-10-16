"""A fake deliverable: each hello case hands Studio a greeting card.

The card text travels in the artifact title, so artifact.get needs no stored
state and still answers after a controller restart.
"""

from __future__ import annotations

from typing import Any

from supervaizer.contracts import V2ActionDefinition

ARTIFACT_TYPE = "greeting_card"
ARTIFACT_TYPES = [{"type": ARTIFACT_TYPE, "label": "Greeting card"}]
# Read-only, so any viewer of the job may open the card.
ARTIFACT_ACTION = V2ActionDefinition(id="artifact.get", mutating=False)


def greeting_card(case_id: str, message: str) -> dict[str, Any]:
    """The step output that Studio lists as the case deliverable."""
    return {"id": f"{case_id}-card", "type": ARTIFACT_TYPE, "title": message, "media_type": "text/markdown"}


def load_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """artifact.get: the card as Markdown, which Studio shows and exports."""
    if artifact.get("type") != ARTIFACT_TYPE:
        return {"status": "error", "effects": [{"type": "artifact.unsupported", "artifact_id": artifact.get("id")}]}
    content = f"# Greeting card\n\n{artifact.get('title') or ''}\n"
    return {"status": "ok", "effects": [{"type": "artifact.loaded", "artifact": {**artifact, "content": content}}]}
