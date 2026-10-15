"""Studio rule checkpoints for the simple agent.

A before and an after checkpoint guard every "Say hello" step. Studio knows a v2
case only once a job_state has projected it, so job.start holds the hello steps
as pending and the checkpoints run on the first job.sync. A paused checkpoint
parks its step as awaiting until Studio pushes rule.checkpoint.resume.
"""

from __future__ import annotations

import asyncio
from typing import Any

from supervaizer import Account, RuleCheckpointGate
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


class RecoveryRequired(RuntimeError):
    """The decision needs the rule gate this process no longer holds."""


def governed(data: dict[str, Any]) -> bool:
    return "rule_snapshot" in (data.get("input") or {})


def open_gate(data: dict[str, Any], job_state: dict[str, Any]) -> None:
    """Keep the Studio gate for this job and hold its hello steps until the gate allows them."""
    gate = RuleCheckpointGate.from_job_start(account, V2ActionRequest.model_validate(data))
    for case in _hello_cases(job_state):
        case["status"] = case["steps"][0]["status"] = "pending"
    _set_job_status(job_state, "active")
    _pending[job_state["job"]["id"]] = {
        "gate": gate,
        "job_state": job_state,
        "cursor": (0, "before"),
        "waiter": None,
    }


async def sync(job_id: str) -> dict[str, Any] | None:
    """Run the outstanding checkpoints; None when this process holds no gate for the job."""
    pending = _pending.get(job_id)
    if pending is None:
        return None
    if pending["waiter"] is None:  # not parked on a Studio decision
        await _run(pending)
    return pending["job_state"]


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
        step = case["steps"][0]
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
    return [case for case in job_state["cases"] if case["steps"][0]["id"].endswith("-say-hello")]


def _set_status(job_state: dict[str, Any], case: dict[str, Any], status: str) -> None:
    case["status"] = case["steps"][0]["status"] = status
    _set_job_status(job_state, status)


def _set_job_status(job_state: dict[str, Any], status: str) -> None:
    """A case waiting on a human keeps the job awaiting whatever the hello steps do."""
    cases = job_state["cases"]
    if any(case["status"] == "awaiting" for case in cases):
        status = "awaiting"
    elif status == "completed" and any(case["status"] != "completed" for case in cases):
        status = "active"
    job_state["job"]["status"] = status
