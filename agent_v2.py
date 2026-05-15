"""Supervaizer v2 contract and handlers for the Hello World examples."""

from __future__ import annotations

from typing import Any

from agent_data_resource import (
    _create_contact,
    _delete_contact,
    _import_contacts,
    _list_contacts,
    _update_contact,
)
from supervaizer.contracts import (
    SUPERVAIZER_V2_A2A_VERSION,
    SUPERVAIZER_V2_A2UI_VERSION,
    SUPERVAIZER_V2_CONTRACT_VERSION,
)

SIMPLE_AGENT_SLUG = "hello-world-ai-agent"
HUMAN_LOOP_AGENT_SLUG = "human-in-the-loop-agent"
A2UI_CATALOG_VERSION = "supervaizer-v2-hello-world.0"
CONTACT_ACTIONS = [
    "resource.contacts.list",
    "resource.contacts.create",
    "resource.contacts.update",
    "resource.contacts.delete",
    "resource.contacts.import",
]


def build_simple_agent_v2_registration(agent_version: str) -> dict[str, Any]:
    """Return the v2 registration for the simple Hello World agent."""
    return _registration(
        agent_slug=SIMPLE_AGENT_SLUG,
        display_name="Hello World AI Agent",
        agent_version=agent_version,
        actions=["job.start.preview", "job.start", "job.sync", *CONTACT_ACTIONS],
        surfaces=["job.start", "mission.agent.resource.contacts"],
        resources=[_contacts_resource_definition()],
    )


def build_human_loop_v2_registration(agent_version: str) -> dict[str, Any]:
    """Return the v2 registration for the human-in-the-loop Hello World agent."""
    return _registration(
        agent_slug=HUMAN_LOOP_AGENT_SLUG,
        display_name="Human-in-the-Loop Agent",
        agent_version=agent_version,
        actions=["job.start.preview", "job.start", "job.sync", "step.awaiting.submit"],
        surfaces=["job.start", "case.step.awaiting"],
        resources=[],
    )


def handle_simple_v2_surface(request: Any) -> dict[str, Any]:
    """Load the simple agent's A2UI job-start surface."""
    data = _request_dict(request)
    return _surface_result(
        data,
        {
            "type": "Form",
            "id": "hello_world.job.start",
            "title": "Start Hello World",
            "fields": [
                {
                    "id": "count",
                    "label": "How many times to say hello",
                    "type": "number",
                    "required": True,
                    "default": 3,
                }
            ],
            "submit": {"action": "job.start", "label": "Start"},
            "preview": {"action": "job.start.preview"},
            "state": {"draft_session_id": data.get("draft_session_id")},
        },
    )


def handle_human_loop_v2_surface(request: Any) -> dict[str, Any]:
    """Load job-start or awaiting surfaces for the human-loop agent."""
    data = _request_dict(request)
    if data.get("surface") == "case.step.awaiting":
        document = {
            "type": "Form",
            "id": "hello_world.case.step.awaiting",
            "title": "Human approval",
            "fields": [
                {"id": "approved", "label": "Approved", "type": "boolean", "default": True},
                {"id": "comment", "label": "Comment", "type": "text", "required": False},
            ],
            "submit": {"action": "step.awaiting.submit", "label": "Submit"},
            "state": {"case_id": data.get("case_id"), "step_id": data.get("step_id")},
        }
        return _surface_result(data, document)

    return _surface_result(
        data,
        {
            "type": "Form",
            "id": "hello_world.human_loop.job.start",
            "title": "Start Human Review",
            "fields": [
                {
                    "id": "case_count",
                    "label": "How many cases to run",
                    "type": "number",
                    "required": True,
                    "default": 1,
                }
            ],
            "submit": {"action": "job.start", "label": "Start"},
            "preview": {"action": "job.start.preview"},
            "state": {"draft_session_id": data.get("draft_session_id")},
        },
    )


def handle_simple_v2_action(request: Any) -> dict[str, Any]:
    """Dispatch v2 actions for the simple Hello World agent."""
    data = _request_dict(request)
    action = str(data.get("action") or "")
    if action == "job.start.preview":
        return _ok("job.start.previewed", count=_count(data, default=3))
    if action == "job.start":
        count = _count(data, default=3)
        job_state = _simple_job_state(data, count=count, status="completed")
        return _ok(
            "job.started",
            job_id=job_state["job"]["id"],
            status="completed",
            message=f"Completed {count} hello case(s)",
            job_state=job_state,
        )
    if action == "job.sync":
        count = _count(data, default=1)
        return _ok(
            "job.synced",
            job_state=_simple_job_state(data, count=count, status="completed"),
        )
    if action.startswith("resource.contacts."):
        return _handle_contacts_action(action, _input(data))
    return _error("action.unsupported", action=action)


def handle_human_loop_v2_action(request: Any) -> dict[str, Any]:
    """Dispatch v2 actions for the human-in-the-loop Hello World agent."""
    data = _request_dict(request)
    action = str(data.get("action") or "")
    if action == "job.start.preview":
        return _ok("job.start.previewed", case_count=_count(data, default=1, field="case_count"))
    if action in {"job.start", "job.sync"}:
        job_state = _awaiting_job_state(data)
        return _ok(
            "job.synced" if action == "job.sync" else "job.started",
            job_id=job_state["job"]["id"],
            status="awaiting",
            message="Waiting for human approval",
            job_state=job_state,
        )
    if action == "step.awaiting.submit":
        job_state = _completed_human_loop_state(data)
        return _ok(
            "step.awaiting.submitted",
            job_id=job_state["job"]["id"],
            case_id=data.get("case_id"),
            step_id=data.get("step_id"),
            job_state=job_state,
        )
    return _error("action.unsupported", action=action)


def _registration(
    *,
    agent_slug: str,
    display_name: str,
    agent_version: str,
    actions: list[str],
    surfaces: list[str],
    resources: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "supervaizer_contract_version": SUPERVAIZER_V2_CONTRACT_VERSION,
        "agent": {"id": agent_slug, "slug": agent_slug, "display_name": display_name},
        "versions": {
            "a2ui_version": SUPERVAIZER_V2_A2UI_VERSION,
            "a2ui_catalog_version": A2UI_CATALOG_VERSION,
            "a2a_version": SUPERVAIZER_V2_A2A_VERSION,
            "ag_ui_version": None,
        },
        "a2a": {
            "agent_card_url": f"/.well-known/agents/v{agent_version}/{agent_slug}_agent.json",
            "controller_url": "/a2a",
            "transport": {"json_rpc": True, "sse": True, "push_notifications": False},
            "external_interop": {"inbound_tasks": False, "outbound_delegation": False},
        },
        "capabilities": {
            "surfaces": surfaces,
            "actions": actions,
            "case_lanes": [{"id": "work", "label": "Work", "default": True}],
            "artifact_types": [],
        },
        "job_policy": {
            "offline_start_policy": "block",
            "offline_running_policy": "fail_in_studio",
            "sync": {
                "action": "job.sync",
                "supported_statuses": ["active", "awaiting", "completed"],
            },
        },
        "resources": resources,
        "datasets": [],
    }


def _contacts_resource_definition() -> dict[str, Any]:
    return {
        "id": "contacts",
        "label": "Contacts",
        "auto_surface": True,
        "operations": ["list", "create", "update", "delete", "import"],
        "display": {
            "title_field": "email",
            "columns": ["first_name", "last_name", "email", "city"],
            "search_fields": ["first_name", "last_name", "email", "city"],
        },
        "fields": [
            {"id": "first_name", "label": "First name", "type": "string", "required": True},
            {"id": "last_name", "label": "Last name", "type": "string"},
            {"id": "email", "label": "Email", "type": "email"},
            {"id": "city", "label": "City", "type": "string"},
        ],
    }


def _handle_contacts_action(action: str, data: dict[str, Any]) -> dict[str, Any]:
    if action == "resource.contacts.list":
        items = _list_contacts()
        return _ok("resource.listed", resource="contacts", count=len(items), items=items)
    if action == "resource.contacts.create":
        return _ok("resource.created", resource="contacts", item=_create_contact(data))
    if action == "resource.contacts.update":
        contact_id = str(data.get("id") or data.get("item_id") or "")
        item = _update_contact(contact_id, data)
        if item is None:
            return _error(
                "resource.action.failed",
                resource="contacts",
                message="Contact not found",
            )
        return _ok("resource.updated", resource="contacts", item=item)
    if action == "resource.contacts.delete":
        contact_id = str(data.get("id") or data.get("item_id") or "")
        if not _delete_contact(contact_id):
            return _error(
                "resource.action.failed",
                resource="contacts",
                message="Contact not found",
            )
        return _ok("resource.deleted", resource="contacts", item={"id": contact_id})
    if action == "resource.contacts.import":
        records = data.get("records")
        result = _import_contacts(records if isinstance(records, list) else [])
        return _ok(
            "resource.imported",
            resource="contacts",
            count=result["created"],
            items=_list_contacts(),
            errors=[],
        )
    return _error(
        "resource.action.failed",
        resource="contacts",
        message="Unsupported contact action",
    )


def _simple_job_state(data: dict[str, Any], *, count: int, status: str) -> dict[str, Any]:
    job_id = _job_id(data)
    return {
        "job": _job_snapshot(data, job_id=job_id, status=status, agent_slug=SIMPLE_AGENT_SLUG),
        "cases": [
            {
                "id": f"{job_id}-case-{index}",
                "lane": "work",
                "title": f"Hello case {index}",
                "status": status,
                "steps": [
                    {
                        "id": f"{job_id}-case-{index}-say-hello",
                        "activity": "operation",
                        "status": status,
                        "title": "Say hello",
                    }
                ],
            }
            for index in range(1, count + 1)
        ],
    }


def _awaiting_job_state(data: dict[str, Any]) -> dict[str, Any]:
    job_id = _job_id(data)
    case_id = str(data.get("case_id") or f"{job_id}-case-1")
    step_id = str(data.get("step_id") or f"{case_id}-approval")
    return {
        "job": _job_snapshot(
            data,
            job_id=job_id,
            status="awaiting",
            agent_slug=HUMAN_LOOP_AGENT_SLUG,
        ),
        "cases": [
            {
                "id": case_id,
                "lane": "work",
                "title": "Human review case",
                "status": "awaiting",
                "steps": [
                    {
                        "id": step_id,
                        "activity": "operation",
                        "status": "awaiting",
                        "title": "Human approval",
                        "awaiting": {
                            "reason": "human_input",
                            "surface": "case.step.awaiting",
                            "action": "step.awaiting.submit",
                            "fields": [
                                {
                                    "id": "approved",
                                    "label": "Approved",
                                    "type": "boolean",
                                    "required": True,
                                },
                                {"id": "comment", "label": "Comment", "type": "text"},
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _completed_human_loop_state(data: dict[str, Any]) -> dict[str, Any]:
    state = _awaiting_job_state(data)
    state["job"]["status"] = "completed"
    state["cases"][0]["status"] = "completed"
    state["cases"][0]["steps"][0]["status"] = "completed"
    state["cases"][0]["steps"][0].pop("awaiting", None)
    return state


def _job_snapshot(
    data: dict[str, Any], *, job_id: str, status: str, agent_slug: str
) -> dict[str, Any]:
    return {
        "id": job_id,
        "agent_slug": agent_slug,
        "mission_id": str(data.get("mission_id") or "mission"),
        "status": status,
        "source": {"type": "fresh_start"},
    }


def _surface_result(data: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    return {
        "surface": str(data.get("surface") or "job.start"),
        "a2ui_version": SUPERVAIZER_V2_A2UI_VERSION,
        "a2ui_catalog_version": A2UI_CATALOG_VERSION,
        "document": document,
    }


def _ok(effect_type: str, **effect: Any) -> dict[str, Any]:
    return {"status": "ok", "effects": [{"type": effect_type, **effect}]}


def _error(effect_type: str, **effect: Any) -> dict[str, Any]:
    return {"status": "error", "effects": [{"type": effect_type, **effect}]}


def _count(data: dict[str, Any], *, default: int, field: str = "count") -> int:
    value = _input(data).get(field, default)
    try:
        return max(0, min(int(value), 100))
    except (TypeError, ValueError):
        return default


def _input(data: dict[str, Any]) -> dict[str, Any]:
    value = data.get("input")
    return value if isinstance(value, dict) else {}


def _job_id(data: dict[str, Any]) -> str:
    return str(data.get("job_id") or f"job-{data.get('request_id') or 'hello-world'}")


def _request_dict(request: Any) -> dict[str, Any]:
    if isinstance(request, dict):
        return request
    if hasattr(request, "model_dump"):
        return request.model_dump(mode="python")
    raise TypeError(f"Unsupported request type: {type(request).__name__}")
