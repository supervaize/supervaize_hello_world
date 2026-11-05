"""Job Configurator example: the Configure screen Studio shows on the job page.

Studio loads the ``job.configurator`` surface and draws one tab per section:

- **Parameters** (``Form``): greeting, signature and shout. Its ``save`` binding
  names the action Studio invokes with ``{"revision": ..., "value": {...}}``.
- **Review & send** (``Review``): the readiness checklist and the primary action.
- **Links & exports** (``Table``, schema 2 only): a link and a sample card.

Every mutation quotes the revision it was made from. A stale revision gets a
``configurator.conflict`` effect back and Studio reloads the document.
Guide: https://docs.runwaize.com/docs/supervaizer-controller/job-configurator
"""

from __future__ import annotations

from typing import Any

from agent_deliverable import ARTIFACT_TYPE

CONFIGURATOR_SURFACE = "job.configurator"
CONFIGURE_ACTION = "job.configure"
GREET_ACTION = "job.greet"
# Schema "2" is schema "1" plus the read-only Table component.
SCHEMA_VERSIONS = ("1", "2")
DEFAULT_CONFIG: dict[str, Any] = {"greeting": "Hello", "signature": "", "shout": False}
# Per-job configuration. A save must quote the revision it was made from, so two
# operators cannot silently overwrite each other.
# ponytail: in-memory, lost on restart; a real agent keys this on its job store
_job_configs: dict[str, dict[str, Any]] = {}


def job_config(job_id: str) -> dict[str, Any]:
    """The job's configure-form values plus the revision they were saved at."""
    return _job_configs.get(job_id) or {**DEFAULT_CONFIG, "revision": "0"}


def message(config: dict[str, Any], name: str, city: str) -> str:
    """The greeting a case delivers, shaped by the job's configuration."""
    text = f"{config['greeting']}, {name} from {city}!"
    if config.get("signature"):
        text += f" {config['signature']}"
    return text.upper() if config.get("shout") else text


def readiness(job_id: str) -> list[dict[str, Any]]:
    """What the operator must finish before the primary action; Studio only displays it."""
    config = job_config(job_id)
    return [
        _check("greeting", "Greeting is set", bool(config["greeting"])),
        _check("signature", "Signature is set", bool(config["signature"])),
    ]


def job_display(job_id: str) -> dict[str, str]:
    """Agent vocabulary for Studio's job list and title row (``job_state.job.display``)."""
    display = {"entity_label": "Hello job"}
    if not _ready(job_id):
        # No label once ready: Studio then shows its own job status.
        display["state_label"] = "Draft — setup incomplete"
    return display


def configurator_document(job_id: str, surface_input: dict[str, Any]) -> dict[str, Any]:
    """The A2UI Configurator document for one job, at the highest schema both sides share."""
    supported = surface_input.get("supported_schema_versions") or ["1"]
    schema_version = next((v for v in reversed(SCHEMA_VERSIONS) if v in supported), None)
    if schema_version is None:
        return {
            "type": "ConfiguratorError",
            "code": "unsupported_schema",
            "message": "Studio and agent do not share a Configurator schema version.",
            "supported_schema_versions": list(SCHEMA_VERSIONS),
        }
    config = job_config(job_id)
    sections = [
        _section("parameters", "Parameters", _parameters_form(config)),
        # A Review section lists `readiness` and hosts the primary action.
        _section("review", "Review & send", {"type": "Review", "id": "hello_world.review", "bindings": {}, "data": {}}),
    ]
    if schema_version == "2":
        sections.append(_section("exports", "Links & exports", _exports_table(config)))
    ready = _ready(job_id)
    return {
        "type": "Configurator",
        "id": "hello_world.configurator",
        "schema_version": schema_version,
        "revision": config["revision"],
        "title": "Hello World setup",
        "entity_label": "Hello job",
        "state": "ready" if ready else "draft",
        "sections": sections,
        "readiness": readiness(job_id),
        "primary_action": {
            "id": "greet",
            "label": "Send greetings",
            "status": "enabled" if ready else "disabled",
            "binding": {
                **_binding(GREET_ACTION, "document"),
                "confirmation": {
                    "title": "Send greetings?",
                    "message": "This replaces the job's hello cases with new ones.",
                    "confirm_label": "Send greetings",
                },
            },
        },
    }


def conflict(job_id: str, action_input: dict[str, Any]) -> dict[str, Any] | None:
    """The refusal for an action made from a revision that is no longer current."""
    revision = job_config(job_id)["revision"]
    if action_input.get("revision") == revision:
        return None
    return _result(
        "error", "configurator.conflict", message="Configurator changed; reload required", current_revision=revision
    )


def configure(job_id: str, action_input: dict[str, Any]) -> dict[str, Any]:
    """Save the Parameters form. The agent validates again: Studio's checks are presentation."""
    if stale := conflict(job_id, action_input):
        return stale
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
        "revision": str(int(job_config(job_id)["revision"]) + 1),
    }
    _job_configs[job_id] = saved
    return _result("ok", "job.configured", job_id=job_id, **saved)


def greet_refusal(job_id: str, action_input: dict[str, Any]) -> dict[str, Any] | None:
    """Why the primary action cannot run now; None when it can."""
    if stale := conflict(job_id, action_input):
        return stale
    if not _ready(job_id):
        return _result("error", "job.greet.failed", message="Finish the setup checklist first")
    return None


def _parameters_form(config: dict[str, Any]) -> dict[str, Any]:
    return {
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
                    "description": "The first word of every message.",
                },
                {
                    "id": "signature",
                    "label": "Signature",
                    "type": "text",
                    "required": False,
                    "default": config["signature"],
                    "description": "Added after the greeting. Required before you can send.",
                },
                {
                    "id": "shout",
                    "label": "Shout (uppercase messages)",
                    "type": "boolean",
                    "default": config["shout"],
                },
            ],
            "save_label": "Save parameters",
        },
        "bindings": {"save": _binding(CONFIGURE_ACTION, "component")},
    }


def _exports_table(config: dict[str, Any]) -> dict[str, Any]:
    """Read-only: a Table takes no bindings. A cell is text, a link or an artifact."""
    return {
        "type": "Table",
        "id": "hello_world.exports",
        "bindings": {},
        "data": {
            "title": "Links & exports",
            "empty_label": "Nothing to export yet.",
            "columns": [{"id": "item", "label": "Item"}, {"id": "link", "label": "Link"}],
            "rows": [
                {
                    "item": "Configure screen guide",
                    "link": {
                        "label": "Open",
                        "href": "https://docs.runwaize.com/docs/supervaizer-controller/job-configurator",
                    },
                },
                {
                    "item": "Sample greeting card",
                    # Studio sends this descriptor back verbatim to `artifact.get`.
                    "link": {
                        "label": "View",
                        "artifact": {
                            "id": "hello_world.sample_card",
                            "type": ARTIFACT_TYPE,
                            "title": message(config, "Ada", "Paris"),
                            "media_type": "text/markdown",
                        },
                    },
                },
            ],
        },
    }


def _ready(job_id: str) -> bool:
    return all(item["status"] == "ok" for item in readiness(job_id))


def _check(item_id: str, label: str, ok: bool) -> dict[str, Any]:
    # `section_id` makes the checklist line a link to the section that fixes it.
    return {"id": item_id, "label": label, "status": "ok" if ok else "blocked", "section_id": "parameters"}


def _section(section_id: str, label: str, component: dict[str, Any]) -> dict[str, Any]:
    return {"id": section_id, "label": label, "policy": "editable", "component": component}


def _binding(action_id: str, payload_source: str) -> dict[str, Any]:
    return {"action_id": action_id, "target_scope": "job", "payload_source": payload_source}


def _result(status: str, effect_type: str, **effect: Any) -> dict[str, Any]:
    return {"status": status, "effects": [{"type": effect_type, **effect}]}
