"""Supervaizer v2 contract and handlers for the Hello World examples."""

from __future__ import annotations

import random
from typing import Any

from supervaizer.contracts import (
    SUPERVAIZER_V2_A2UI_VERSION,
    SupervaizerV2AgentRegistrationContract,
    V2ActionDefinition,
    build_v2_agent_registration,
)

import agent_rules
from agent_configurator import (
    CONFIGURATOR_SURFACE,
    CONFIGURE_ACTION,
    configurator_document,
    configure,
    job_config,
)
from agent_dashboard import (
    ANALYTICS_SURFACE,
    DATASET_QUERY_ACTION,
    analytics_document,
    dataset_definition,
    query_dataset,
)
from agent_data_resource import (
    _create_contact,
    _delete_contact,
    _import_contacts,
    _list_contacts,
    _update_contact,
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
# A bare action id is mutating=True (fail closed); the two read-only actions say so.
# Resource operation ids are freeform, so the SDK cannot derive that list is read-only.
_PREVIEW_ACTION = V2ActionDefinition(id="job.start.preview", mutating=False)
_CONTACTS_LIST_ACTION = V2ActionDefinition(
    id="resource.contacts.list", mutating=False, scope="workspace"
)
AWAITING_SURFACE = "case.step.awaiting"
AWAITING_SUBMIT_ACTION = "step.awaiting.submit"
AWAITING_FIELDS = [
    {"id": "approved", "label": "Approved", "type": "boolean", "required": True},
    {"id": "comment", "label": "Comment", "type": "text"},
]
# Random case content, so every run looks different in Studio.
NAMES = ("Ada", "Grace", "Linus", "Margaret", "Alan", "Hedy")
CITIES = ("Paris", "Lisbon", "Nairobi", "Kyoto", "Montréal", "Tallinn")
# Studio retries a scheduled firing with the same idempotency_key; it must get
# the original job back, not a second one.
# ponytail: in-memory, lost on restart; a real agent keys this on its job store
_started_jobs: dict[str, dict[str, Any]] = {}
# Per-job state, so job.sync and step.awaiting.submit see what job.start created.
# ponytail: in-memory; after a restart the submit rebuilds the review case from ids
_jobs: dict[str, dict[str, Any]] = {}


def build_simple_agent_v2_registration(
    agent_version: str,
) -> SupervaizerV2AgentRegistrationContract:
    """Return the v2 registration for the simple Hello World agent."""
    return _registration(
        agent_slug=SIMPLE_AGENT_SLUG,
        display_name="Hello World AI Agent",
        agent_version=agent_version,
        # The SDK derives the other contact actions and the contacts surface
        # from the resource definition.
        actions=[
            _PREVIEW_ACTION,
            "job.start",
            "job.sync",
            AWAITING_SUBMIT_ACTION,
            CONFIGURE_ACTION,
            _CONTACTS_LIST_ACTION,
        ],
        surfaces=["job.start", AWAITING_SURFACE, CONFIGURATOR_SURFACE, ANALYTICS_SURFACE],
        resources=[_contacts_resource_definition()],
        # The SDK derives dataset.hello_cases.query and the dataset surface.
        datasets=[dataset_definition()],
        scheduled_start=True,
        # Lets Studio start this agent in a mission with rules; the SDK adds
        # the rule.checkpoint.resume action (job scope) that Studio requires.
        rule_checkpoints={"phases": agent_rules.PHASES},
    )


def build_human_loop_v2_registration(
    agent_version: str,
) -> SupervaizerV2AgentRegistrationContract:
    """Return the v2 registration for the human-in-the-loop Hello World agent."""
    return _registration(
        agent_slug=HUMAN_LOOP_AGENT_SLUG,
        display_name="Human-in-the-Loop Agent",
        agent_version=agent_version,
        actions=[_PREVIEW_ACTION, "job.start", "job.sync", "step.awaiting.submit"],
        surfaces=["job.start", "case.step.awaiting"],
        resources=[],
    )


def handle_simple_v2_surface(request: Any) -> dict[str, Any]:
    """Load the simple agent's A2UI job-start or configurator surface."""
    data = _request_dict(request)
    if data.get("surface") == CONFIGURATOR_SURFACE:
        return _surface_result(data, configurator_document(_job_id(data), _input(data)))
    if data.get("surface") == AWAITING_SURFACE:
        return _surface_result(data, _awaiting_document(data))
    if data.get("surface") == ANALYTICS_SURFACE:
        return _surface_result(data, analytics_document(_input(data)))
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
                },
                {
                    "id": "add_human_in_the_loop",
                    "label": "Add human in the loop",
                    "type": "boolean",
                    "default": False,
                },
            ],
            "submit": {"action": "job.start", "label": "Start"},
            "preview": {"action": "job.start.preview"},
            "state": {"draft_session_id": data.get("draft_session_id")},
        },
    )


def handle_human_loop_v2_surface(request: Any) -> dict[str, Any]:
    """Load job-start or awaiting surfaces for the human-loop agent."""
    data = _request_dict(request)
    if data.get("surface") == AWAITING_SURFACE:
        return _surface_result(data, _awaiting_document(data))

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


async def handle_simple_v2_action(request: Any) -> dict[str, Any]:
    """Dispatch v2 actions for the simple Hello World agent."""
    data = _request_dict(request)
    action = str(data.get("action") or "")
    if action == "job.start.preview":
        return _ok("job.start.previewed", count=_count(data, default=3))
    if action == "job.start":
        idempotency_key = data.get("idempotency_key")
        if idempotency_key in _started_jobs:
            return _started_jobs[idempotency_key]
        count = _count(data, default=3)
        with_human = _flag(data, "add_human_in_the_loop")
        job_state = _simple_job_state(data, count=count, with_human=with_human)
        _jobs[job_state["job"]["id"]] = job_state
        message = _start_message(count, data.get("schedule"), with_human)
        if agent_rules.governed(data):
            # Studio knows the cases only after this response, so the rule
            # checkpoints run on the first job.sync.
            agent_rules.open_gate(data, job_state)
            message = f"{count} hello case(s) held for Studio rule checkpoints"
        result = _ok(
            "job.started",
            job_id=job_state["job"]["id"],
            status=job_state["job"]["status"],
            message=message,
            job_state=job_state,
        )
        if idempotency_key:
            _started_jobs[idempotency_key] = result
        return result
    if action == "job.sync":
        try:
            job_state = await agent_rules.sync(_job_id(data))
        except RuntimeError as error:  # Studio refused or lost a checkpoint call
            return _error("job.sync.failed", job_id=_job_id(data), message=str(error))
        job_state = job_state or _jobs.get(_job_id(data)) or _simple_job_state(
            data, count=_count(data, default=1), with_human=False
        )
        return _ok("job.synced", job_state=job_state)
    if action == agent_rules.RESUME_ACTION:
        return await _resume_rule_checkpoint(data)
    if action == AWAITING_SUBMIT_ACTION:
        job_state = _submit_review(data)
        return _ok(
            "step.awaiting.submitted",
            job_id=job_state["job"]["id"],
            case_id=data.get("case_id"),
            step_id=data.get("step_id"),
            job_state=job_state,
        )
    if action == CONFIGURE_ACTION:
        return configure(_job_id(data), _input(data))
    if action == DATASET_QUERY_ACTION:
        return query_dataset(_jobs, _input(data))
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
    actions: list[str | V2ActionDefinition],
    surfaces: list[str],
    resources: list[dict[str, Any]],
    datasets: list[dict[str, Any]] = (),
    scheduled_start: bool = False,
    rule_checkpoints: dict[str, Any] | None = None,
) -> SupervaizerV2AgentRegistrationContract:
    return build_v2_agent_registration(
        agent_slug=agent_slug,
        display_name=display_name,
        a2ui_catalog_version=A2UI_CATALOG_VERSION,
        # The builder defaults to the unversioned card route; this example
        # serves the versioned one.
        agent_card_url=f"/.well-known/agents/v{agent_version}/{agent_slug}_agent.json",
        surfaces=surfaces,
        actions=actions,
        resources=resources,
        datasets=datasets,
        case_lanes=[{"id": "work", "label": "Work", "default": True}],
        # Lets Studio start this agent on a cron schedule (Studio owns the
        # clock and calls the normal job.start). Omitted on the wire when False.
        scheduled_start=scheduled_start,
        rule_checkpoints=rule_checkpoints,
        job_policy={
            "sync": {
                "action": "job.sync",
                "supported_statuses": ["active", "awaiting", "completed"],
            }
        },
    )


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


def _simple_job_state(data: dict[str, Any], *, count: int, with_human: bool) -> dict[str, Any]:
    """`count` completed hello cases, plus one awaiting review case when asked for."""
    job_id = _job_id(data)
    config = job_config(job_id)
    cases = [_hello_case(job_id, index, config) for index in range(1, count + 1)]
    if with_human:
        cases.append(_review_case(f"{job_id}-case-review"))
    status = "awaiting" if with_human else "completed"
    return {
        "job": _job_snapshot(data, job_id=job_id, status=status, agent_slug=SIMPLE_AGENT_SLUG),
        "cases": cases,
    }


def _hello_case(job_id: str, index: int, config: dict[str, Any]) -> dict[str, Any]:
    name, city = random.choice(NAMES), random.choice(CITIES)
    message = f"{config['greeting']}, {name} from {city}!"
    if config.get("signature"):
        message += f" {config['signature']}"
    if config.get("shout"):
        message = message.upper()
    return {
        "id": f"{job_id}-case-{index}",
        "lane": "work",
        "title": f"{config['greeting']} {name} ({index})",
        "status": "completed",
        "metadata": {"name": name, "city": city, "message": message},
        "steps": [
            {
                "id": f"{job_id}-case-{index}-say-hello",
                "activity": "operation",
                "status": "completed",
                "title": "Say hello",
            }
        ],
    }


def _review_case(case_id: str, step_id: str | None = None) -> dict[str, Any]:
    return {
        "id": case_id,
        "lane": "work",
        "title": "Human review case",
        "status": "awaiting",
        "metadata": {},
        "steps": [
            {
                "id": step_id or f"{case_id}-approval",
                "activity": "operation",
                "status": "awaiting",
                "title": "Human approval",
                "awaiting": {
                    "reason": "human_input",
                    "surface": AWAITING_SURFACE,
                    "action": AWAITING_SUBMIT_ACTION,
                    "fields": AWAITING_FIELDS,
                },
            }
        ],
    }


def _complete_review(case: dict[str, Any], submitted: dict[str, Any]) -> None:
    case["status"] = "completed"
    case["metadata"].update(
        approved=bool(submitted.get("approved", True)),
        comment=str(submitted.get("comment") or ""),
    )
    for step in case["steps"]:
        step["status"] = "completed"
        step.pop("awaiting", None)


def _submit_review(data: dict[str, Any]) -> dict[str, Any]:
    """Complete the review case the submit names; the job completes when nothing awaits."""
    job_id = _job_id(data)
    case_id = str(data.get("case_id") or f"{job_id}-case-review")
    job_state = _jobs.get(job_id) or {
        # Unknown job (restart): the hello cases completed at start, only the
        # review case is rebuilt, from the ids Studio sends back.
        "job": _job_snapshot(data, job_id=job_id, status="awaiting", agent_slug=SIMPLE_AGENT_SLUG),
        "cases": [_review_case(case_id, data.get("step_id"))],
    }
    for case in job_state["cases"]:
        if case["id"] == case_id:
            _complete_review(case, _input(data))
    if all(case["status"] == "completed" for case in job_state["cases"]):
        job_state["job"]["status"] = "completed"
    _jobs[job_id] = job_state
    return job_state


async def _resume_rule_checkpoint(data: dict[str, Any]) -> dict[str, Any]:
    """Apply Studio's checkpoint decision; a decision for another gate fails closed."""
    try:
        job_state = await agent_rules.resume(data)
    except (ValueError, RuntimeError) as error:  # ValidationError is a ValueError
        return _error("rule.checkpoint.rejected", job_id=data.get("job_id"), message=str(error))
    _jobs[job_state["job"]["id"]] = job_state
    return _ok(
        "rule.checkpoint.resumed",
        job_id=job_state["job"]["id"],
        status=job_state["job"]["status"],
        job_state=job_state,
    )


def _awaiting_document(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Form",
        "id": "hello_world.case.step.awaiting",
        "title": "Human approval",
        "fields": [
            {"id": "approved", "label": "Approved", "type": "boolean", "default": True},
            {"id": "comment", "label": "Comment", "type": "text", "required": False},
        ],
        "submit": {"action": AWAITING_SUBMIT_ACTION, "label": "Submit"},
        "state": {"case_id": data.get("case_id"), "step_id": data.get("step_id")},
    }


def _awaiting_job_state(data: dict[str, Any]) -> dict[str, Any]:
    job_id = _job_id(data)
    case_id = str(data.get("case_id") or f"{job_id}-case-1")
    return {
        "job": _job_snapshot(
            data,
            job_id=job_id,
            status="awaiting",
            agent_slug=HUMAN_LOOP_AGENT_SLUG,
        ),
        "cases": [_review_case(case_id, data.get("step_id"))],
    }


def _completed_human_loop_state(data: dict[str, Any]) -> dict[str, Any]:
    state = _awaiting_job_state(data)
    _complete_review(state["cases"][0], _input(data))
    state["job"]["status"] = "completed"
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


def _start_message(count: int, schedule: Any, with_human: bool = False) -> str:
    """Name the Studio schedule when the start was a scheduled firing."""
    message = f"Completed {count} hello case(s)"
    if with_human:
        message += ", 1 case awaits human review"
    if isinstance(schedule, dict):
        name = schedule.get("schedule_name") or schedule.get("schedule_id")
        message += f" for schedule {name} (run {schedule.get('run_number')})"
    return message


def _count(data: dict[str, Any], *, default: int, field: str = "count") -> int:
    value = _input(data).get(field, default)
    try:
        return max(0, min(int(value), 100))
    except (TypeError, ValueError):
        return default


def _flag(data: dict[str, Any], field: str) -> bool:
    value = _input(data).get(field, False)
    return value is True or str(value).lower() in {"true", "1", "yes"}


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
