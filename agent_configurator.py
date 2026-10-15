"""Job Configurator example: Studio edits a per-job greeting through an A2UI Configurator.

Studio renders the ``job.configurator`` surface on the job page. A section's
``save`` binding names the action Studio invokes with
``{"revision": ..., "value": {...field values}}``. A stale revision gets a
``configurator.conflict`` effect back and Studio reloads the document.
"""

from __future__ import annotations

from typing import Any

CONFIGURATOR_SURFACE = "job.configurator"
CONFIGURE_ACTION = "job.configure"
DEFAULT_CONFIG: dict[str, Any] = {"greeting": "Hello", "signature": "", "shout": False}
# Per-job configuration. A save must quote the revision it was made from, so two
# operators cannot silently overwrite each other.
# ponytail: in-memory, lost on restart; a real agent keys this on its job store
_job_configs: dict[str, dict[str, Any]] = {}


def greeting(job_id: str) -> str:
    """The greeting the job's cases use."""
    return str(job_config(job_id)["greeting"])


def job_config(job_id: str) -> dict[str, Any]:
    """The job's configure-form values plus the revision they were saved at."""
    return _job_configs.get(job_id) or {**DEFAULT_CONFIG, "revision": "0"}


def configurator_document(job_id: str, surface_input: dict[str, Any]) -> dict[str, Any]:
    """A2UI Configurator for one job: one editable section, the configure form."""
    supported = surface_input.get("supported_schema_versions") or ["1"]
    if "1" not in supported:
        return {
            "type": "ConfiguratorError",
            "code": "unsupported_schema",
            "message": "Studio and agent do not share a Configurator schema version.",
            "supported_schema_versions": ["1"],
        }
    config = job_config(job_id)
    return {
        "type": "Configurator",
        "id": "hello_world.configurator",
        "schema_version": "1",
        "revision": config["revision"],
        "title": "Hello World setup",
        "sections": [
            {
                "id": "greeting",
                "label": "Greeting",
                "policy": "editable",
                "component": {
                    "type": "Form",
                    "id": "hello_world.greeting",
                    "data": {
                        "fields": [
                            {
                                "id": "greeting",
                                "label": "Greeting",
                                "type": "text",
                                "required": True,
                                "default": config["greeting"],
                            },
                            {
                                "id": "signature",
                                "label": "Signature",
                                "type": "text",
                                "required": False,
                                "default": config["signature"],
                            },
                            {
                                "id": "shout",
                                "label": "Shout (uppercase messages)",
                                "type": "boolean",
                                "default": config["shout"],
                            },
                        ],
                        "save_label": "Save configuration",
                    },
                    "bindings": {
                        "save": {
                            "action_id": CONFIGURE_ACTION,
                            "target_scope": "job",
                            "payload_source": "component",
                        }
                    },
                },
            }
        ],
        "readiness": [
            {"id": "greeting", "label": "Greeting is set", "status": "ok", "section_id": "greeting"}
        ],
        "primary_action": None,
    }


def configure(job_id: str, action_input: dict[str, Any]) -> dict[str, Any]:
    """Save the form; refuse a save made from a revision that is no longer current."""
    config = job_config(job_id)
    if action_input.get("revision") != config["revision"]:
        return _result(
            "error",
            "configurator.conflict",
            message="Configurator changed; reload required",
            current_revision=config["revision"],
        )
    value = action_input.get("value")
    value = value if isinstance(value, dict) else {}
    new_greeting = str(value.get("greeting") or "").strip()
    if not new_greeting:
        return _result("error", "job.configure.failed", message="Greeting is required")
    shout = value.get("shout")
    saved = {
        "greeting": new_greeting,
        "signature": str(value.get("signature") or "").strip(),
        "shout": shout is True or str(shout).lower() == "true",
        "revision": str(int(config["revision"]) + 1),
    }
    _job_configs[job_id] = saved
    return _result("ok", "job.configured", job_id=job_id, **saved)


def _result(status: str, effect_type: str, **effect: Any) -> dict[str, Any]:
    return {"status": status, "effects": [{"type": effect_type, **effect}]}
