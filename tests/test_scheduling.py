# supervaize_hello_world/tests/test_scheduling.py
"""Scheduled start: Studio may start the simple agent on a cron schedule.

Studio owns the clock (studio PR #917). It calls the normal ``job.start`` with a
stable ``idempotency_key`` per occurrence and, because the agent advertises
``capabilities.scheduled_start``, a top-level ``schedule`` object.
"""
from supervaizer.contracts import SupervaizerV2AgentRegistrationContract

from agent_v2 import build_simple_agent_v2_registration
from tests.test_data_resource_e2e import _a2a_request, _action_payload

SCHEDULE = {
    "schedule_id": "sched-1",
    "schedule_name": "Hourly hello",
    "run_id": "run-7",
    "run_number": 7,
    "occurrence_at": "2026-10-15T09:00:00+00:00",
    "trigger": "schedule",
    "cron_expression": "0 * * * *",
    "timezone": "Europe/Paris",
    "error_policy": "interrupt",
}


def test_registration_advertises_scheduled_start():
    """The simple agent opts in; the SDK serializes the capability on the wire."""
    registration = SupervaizerV2AgentRegistrationContract.model_validate(
        build_simple_agent_v2_registration("1.0")
    )
    assert registration.capabilities.scheduled_start is True
    assert registration.model_dump(mode="json")["capabilities"]["scheduled_start"] is True


def test_scheduled_firing_is_idempotent_and_names_the_schedule(client):
    """A retry with the same idempotency_key returns the original job, not a second one."""
    from supervaizer_control import simple_agent

    payload = _action_payload(
        simple_agent.slug, action="job.start", action_input={"count": 2}, job_id="job-sched-7"
    )
    payload["idempotency_key"] = "sched-1:run-7"
    payload["schedule"] = SCHEDULE
    request = _a2a_request(method="supervaizer/action.invoke", params=payload)

    first = client.post("/a2a", json=request).json()["result"]
    retry = client.post("/a2a", json=request).json()["result"]

    effect = first["effects"][0]
    assert effect["type"] == "job.started"
    assert effect["job_id"] == "job-sched-7"
    assert effect["message"] == "Completed 2 hello case(s) for schedule Hourly hello (run 7)"
    assert len(first["job_state"]["cases"]) == 2
    assert retry == first
