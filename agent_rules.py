"""Studio rule checkpoints for the simple agent.

A before and an after checkpoint guard every "Say hello" step. Studio knows a v2
case only once a job_state has projected it, so job.start holds the hello steps
as pending and the checkpoints run on the first job.sync, which the agent asks
Studio for. A paused checkpoint parks its step as awaiting until Studio pushes
rule.checkpoint.resume.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from supervaizer import Account, RuleCheckpointGate
from supervaizer.common import log
from supervaizer.contracts import (
    RuleCheckpointResponse,
    RuleCheckpointResume,
    V2ActionRequest,
)
from supervaizer.rule_controls import resume_rule_checkpoint

RESUME_ACTION = "rule.checkpoint.resume"
PHASES = ["before", "after"]
# The decision is taken in Studio's guardrails UI. The awaiting contract still
# needs a surface and an action: the declared review surface and the real resume action.
AWAITING = {"reason": "rule_checkpoint", "surface": "case.step.awaiting", "action": RESUME_ACTION}
# The gate posts checkpoints with these Studio credentials; supervaizer_control.py sets it.
account: Account | None = None
# ponytail: in-memory per job; a restart loses the gate and its snapshot token,
# so a decision that arrives after one is rejected. A real agent persists both.
_pending: dict[str, dict[str, Any]] = {}
REFRESH_EVENT = "supervaizer.v2.job.refresh_requested"
# ponytail: a fixed wait, so Studio has applied the job.start result and knows the
# cases before its job.sync runs the checkpoints. A slower Studio rejects the
# checkpoints and the job waits for a manual Update, as it did before.
REFRESH_DELAY_SECONDS = 2.0
_refresh_client = httpx.AsyncClient(timeout=30.0)
_refresh_tasks: set[asyncio.Task] = set()


class RecoveryRequired(RuntimeError):
    """The decision needs the rule gate this process no longer holds."""


def governed(data: dict[str, Any]) -> bool:
    return "rule_snapshot" in (data.get("input") or {})


def open_gate(data: dict[str, Any], job_state: dict[str, Any]) -> None:
    """Keep the Studio gate for this job and hold its hello steps until the gate allows them."""
    gate = RuleCheckpointGate.from_job_start(account, V2ActionRequest.model_validate(data))
    # The greeting card appears only once its step runs, so a stopped case delivers nothing.
    held_outputs = {}
    for case in _hello_cases(job_state):
        case["status"] = "pending"
        for step in case["steps"]:
            step["status"] = "pending"
        held_outputs[case["id"]] = _hello_step(case).pop("outputs", [])
    _set_job_status(job_state, "active")
    _pending[job_state["job"]["id"]] = {
        "gate": gate,
        "job_state": job_state,
        "cursor": (0, "before"),
        "waiter": None,
        "outputs": held_outputs,
    }
    schedule_refresh(job_state["job"]["id"])


def schedule_refresh(job_id: str) -> None:
    """Ask Studio, in the background, to sync the job: Studio never polls a v2 job."""
    task = asyncio.get_running_loop().create_task(_request_refresh(job_id))
    _refresh_tasks.add(task)  # the loop keeps only weak references to tasks
    task.add_done_callback(_refresh_tasks.discard)


async def _request_refresh(job_id: str) -> None:
    await asyncio.sleep(REFRESH_DELAY_SECONDS)
    # Async on purpose: Studio handles the event inline and calls job.sync on this
    # process before it answers, so a blocking post would freeze the event loop.
    try:
        response = await _refresh_client.post(
            account.url_event,
            headers=account.api_headers,
            json={
                "source": {"job": job_id},
                "workspace": account.workspace_id,
                "event_type": REFRESH_EVENT,
                "object_type": "job",
                "details": {"reason": "rule_checkpoints"},
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        log.warning(f"[Rules] Studio did not sync job {job_id}; it waits for a manual Update: {error}")


async def sync(job_id: str) -> dict[str, Any] | None:
    """Run the outstanding checkpoints; None when this process holds no gate for the job."""
    pending = _pending.get(job_id)
    if pending is None:
        return None
    if pending["waiter"] is None:  # not parked on a Studio decision
        await _run(pending)
    return pending["job_state"]


def stop(job_id: str) -> None:
    """Drop the gate of a stopped job and cancel a checkpoint parked on Studio."""
    pending = _pending.pop(job_id, None)
    if pending and pending["waiter"] is not None:
        pending["waiter"].cancel()


async def resume(data: dict[str, Any]) -> dict[str, Any]:
    """Apply Studio's decision to the parked step, then run the remaining checkpoints."""
    decision = RuleCheckpointResume.model_validate(
        data["input"] | {key: data.get(key) for key in ("job_id", "case_id", "agent_slug")}
    )
    pending = _pending.get(decision.job_id)
    if pending is None:
        raise RecoveryRequired("this process holds no rule gate for the job")
    # The SDK matches the decision to the live gate (snapshot, agent, occurrence) and wakes it.
    if pending["waiter"] is None or resume_rule_checkpoint(decision) is None:
        raise ValueError("no checkpoint of this job waits for that decision")
    response = await pending["waiter"]
    pending["waiter"] = None
    await _run(pending, response)
    return pending["job_state"]


async def _run(pending: dict[str, Any], decision: RuleCheckpointResponse | None = None) -> None:
    """Walk the hello steps from the cursor; park on a pause, fail on a stop."""
    gate, job_state = pending["gate"], pending["job_state"]
    job_id, cases = job_state["job"]["id"], _hello_cases(job_state)
    while pending["cursor"][0] < len(cases):
        index, phase = pending["cursor"]
        case = cases[index]
        step = _hello_step(case)
        if decision is None:
            decision = await gate.checkpoint(
                occurrence_id=step["id"],
                phase=phase,
                job_id=job_id,
                case_id=case["id"],
                step_id=step["id"],
                context=_context(case, phase),
            )
        if decision.status == "pause":
            _set_status(job_state, case, "awaiting")
            step["awaiting"] = dict(AWAITING)
            pending["waiter"] = asyncio.ensure_future(
                gate.wait_for_resume(decision, step["id"], phase, job_id=job_id, case_id=case["id"])
            )
            await asyncio.sleep(0)  # the waiter registers before Studio can push a decision
            return
        if decision.status == "stop":
            # Studio treats a stop as final: no decision resumes it.
            _set_status(job_state, case, "failed")
            _pending.pop(job_id, None)
            return
        decision = None
        step.pop("awaiting", None)
        if phase == "before":
            # ponytail: the effect is the greeting already in case.metadata
            case["steps"][0]["status"] = "completed"  # Start
            step["outputs"] = pending["outputs"].pop(case["id"])
            _set_status(job_state, case, "active")
            pending["cursor"] = (index, "after")
        else:
            _set_status(job_state, case, "completed")
            pending["cursor"] = (index + 1, "before")
    _pending.pop(job_id, None)
    _set_job_status(job_state, "completed")


def _context(case: dict[str, Any], phase: str) -> dict[str, Any]:
    """The business context Studio's rule controller judges: the greeting is the whole effect."""
    context = {"operation": "say_hello", **case["metadata"]}
    if phase == "after":
        context["outcome"] = "delivered"
    return context


def _hello_cases(job_state: dict[str, Any]) -> list[dict[str, Any]]:
    return [case for case in job_state["cases"] if _hello_step(case)["id"].endswith("-say-hello")]


def _hello_step(case: dict[str, Any]) -> dict[str, Any]:
    """The guarded step: the last one, after Start."""
    return case["steps"][-1]


def _set_status(job_state: dict[str, Any], case: dict[str, Any], status: str) -> None:
    case["status"] = _hello_step(case)["status"] = status
    _set_job_status(job_state, status)


def _set_job_status(job_state: dict[str, Any], status: str) -> None:
    """A case waiting on a human keeps the job awaiting whatever the hello steps do."""
    cases = job_state["cases"]
    if any(case["status"] == "awaiting" for case in cases):
        status = "awaiting"
    elif status == "completed" and any(case["status"] != "completed" for case in cases):
        status = "active"
    job_state["job"]["status"] = status
