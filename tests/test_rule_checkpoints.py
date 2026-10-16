# supervaize_hello_world/tests/test_rule_checkpoints.py
"""Studio rule checkpoints: a before and an after gate around each "Say hello" step.

Studio sends an opaque ``rule_snapshot`` with ``job.start`` when the mission has
rules. The agent holds the hello steps, posts the checkpoints through the SDK
gate on ``job.sync``, parks a paused step as awaiting and continues on
``rule.checkpoint.resume``. ``FakeStudio`` plays Studio's checkpoint endpoint.
"""
from types import SimpleNamespace

import pytest
from supervaizer import rule_controls
from supervaizer.contracts import SupervaizerV2AgentRegistrationContract

import agent_rules
from agent_v2 import build_simple_agent_v2_registration
from tests.test_hitl import _invoke

SNAPSHOT = {
    "hash": "snapshot-1",
    "checkpoint_url": "https://studio.example/api/v1/rule-checkpoints/",
    "version": 1,
    "checkpoint_token": "token-1",
}


class FakeStudio:
    """Answers the gate's checkpoint posts with scripted decisions, in order."""

    def __init__(self, *decisions):
        self.decisions, self.posts, self.answers, self.refreshes = list(decisions), [], [], []

    async def post(self, url, *, headers, json):
        self.posts.append({"url": url, "headers": headers, "body": json})
        answer = {
            "checkpoint_id": f"{json['occurrence_id']}:{json['phase']}",
            "status": self.decisions.pop(0),
            "snapshot_hash": json["snapshot_hash"],
            "input_hash": f"input-{len(self.posts)}",
        }
        self.answers.append(answer)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: answer)


@pytest.fixture
def studio(monkeypatch):
    def install(*decisions):
        fake = FakeStudio(*decisions)
        monkeypatch.setattr(rule_controls._httpx_client, "post", fake.post)
        # Records the refresh request instead of a background post to Studio.
        monkeypatch.setattr(agent_rules, "schedule_refresh", fake.refreshes.append)
        return fake

    return install


def _start(client, job_id, count=2, **action_input):
    from supervaizer_control import simple_agent

    return _invoke(client, simple_agent.slug, action="job.start", action_input={"count": count, **action_input}, job_id=job_id)


def _sync(client, job_id):
    from supervaizer_control import simple_agent

    return _invoke(client, simple_agent.slug, action="job.sync", job_id=job_id)


def _resume(client, fake, job_id, case, status="allow", **overrides):
    """Push the decision for the last checkpoint the fake answered, as Studio does."""
    from supervaizer_control import simple_agent

    answer, step_id = fake.answers[-1], case["steps"][-1]["id"]
    decision = {
        "checkpoint_id": answer["checkpoint_id"],
        "occurrence_id": step_id,
        "phase": fake.posts[-1]["body"]["phase"],
        "status": status,
        "snapshot_hash": answer["snapshot_hash"],
        "input_hash": answer["input_hash"],
        "decision_id": "decision-1",
        **overrides,
    }
    return _invoke(
        client,
        simple_agent.slug,
        action="rule.checkpoint.resume",
        action_input=decision,
        job_id=job_id,
        case_id=case["id"],
        step_id=step_id,
    )


def test_registration_declares_rule_checkpoints_and_the_resume_action():
    """Studio admission requires version 1, the phases its rules use and a job-scoped resume action."""
    registration = SupervaizerV2AgentRegistrationContract.model_validate(
        build_simple_agent_v2_registration("1.0")
    )
    capabilities = registration.model_dump(mode="json")["capabilities"]
    assert capabilities["rule_checkpoints"]["version"] == 1
    assert capabilities["rule_checkpoints"]["phases"] == ["before", "after"]
    resume = next(action for action in capabilities["actions"] if action["id"] == "rule.checkpoint.resume")
    assert resume["scope"] == "job"
    assert resume["mutating"] is True


def test_start_without_rules_completes_at_once(client, studio):
    fake = studio()

    started = _start(client, "job-rules-0")

    assert started["status"] == "completed"
    assert fake.posts == []
    assert fake.refreshes == []
    assert _sync(client, "job-rules-0")["job_state"]["job"]["status"] == "completed"


def test_allowed_checkpoints_complete_the_job_on_sync(client, studio):
    fake = studio("allow", "allow", "allow", "allow")

    started = _start(client, "job-rules-1", rule_snapshot=SNAPSHOT)

    assert started["status"] == "active"
    assert started["message"] == "2 hello case(s) held for Studio rule checkpoints"
    assert [case["steps"][-1]["status"] for case in started["job_state"]["cases"]] == ["pending", "pending"]
    assert all(case["steps"][-1]["outputs"] == [] for case in started["job_state"]["cases"])  # no card yet
    assert fake.posts == []  # Studio projects the cases from this response first
    assert fake.refreshes == ["job-rules-1"]  # then the agent asks Studio for the job.sync

    state = _sync(client, "job-rules-1")["job_state"]

    assert state["job"]["status"] == "completed"
    assert all(case["status"] == "completed" for case in state["cases"])
    assert all(case["steps"][-1]["outputs"][0]["type"] == "greeting_card" for case in state["cases"])
    steps = [case["steps"][-1]["id"] for case in state["cases"]]
    assert [(post["body"]["phase"], post["body"]["step_id"]) for post in fake.posts] == [
        ("before", steps[0]),
        ("after", steps[0]),
        ("before", steps[1]),
        ("after", steps[1]),
    ]
    first = fake.posts[0]
    assert first["url"] == f"{agent_rules.account.api_url}/api/v1/rule-checkpoints/"
    assert first["headers"]["X-Rule-Checkpoint-Token"] == "token-1"
    assert first["body"]["occurrence_id"] == steps[0]
    assert first["body"]["case_id"] == state["cases"][0]["id"]
    assert first["body"]["context"]["operation"] == "say_hello"
    assert first["body"]["context"]["message"] == state["cases"][0]["metadata"]["message"]
    assert fake.posts[1]["body"]["context"]["outcome"] == "delivered"


def test_paused_checkpoint_parks_the_step_until_studio_resumes(client, studio):
    fake = studio("pause", "allow", "allow", "allow")
    _start(client, "job-rules-2", rule_snapshot=SNAPSHOT)

    state = _sync(client, "job-rules-2")["job_state"]

    case = state["cases"][0]
    assert state["job"]["status"] == "awaiting"
    assert case["status"] == "awaiting"
    assert case["steps"][-1]["awaiting"] == {
        "reason": "rule_checkpoint",
        "surface": "case.step.awaiting",
        "action": "rule.checkpoint.resume",
        "fields": [],
        "reopenable": False,
    }
    assert state["cases"][1]["steps"][-1]["status"] == "pending"
    # Another sync reports the same state and posts nothing while Studio decides.
    assert _sync(client, "job-rules-2")["job_state"] == state
    assert len(fake.posts) == 1

    rejected = _resume(client, fake, "job-rules-2", case, snapshot_hash="snapshot-other")

    assert rejected["type"] == "rule.checkpoint.rejected"
    assert _sync(client, "job-rules-2")["job_state"]["job"]["status"] == "awaiting"

    resumed = _resume(client, fake, "job-rules-2", case)

    assert resumed["type"] == "rule.checkpoint.resumed"
    assert resumed["job_state"]["job"]["status"] == "completed"
    assert all(step["status"] == "completed" for c in resumed["job_state"]["cases"] for step in c["steps"])
    assert "awaiting" not in resumed["job_state"]["cases"][0]["steps"][-1]
    assert [post["body"]["phase"] for post in fake.posts] == ["before", "after", "before", "after"]
    assert _sync(client, "job-rules-2")["job_state"] == resumed["job_state"]


def test_denied_checkpoint_fails_the_step(client, studio):
    fake = studio("allow", "pause")
    _start(client, "job-rules-3", count=1, rule_snapshot=SNAPSHOT)
    state = _sync(client, "job-rules-3")["job_state"]
    assert state["cases"][0]["steps"][-1]["status"] == "awaiting"

    denied = _resume(client, fake, "job-rules-3", state["cases"][0], status="stop")

    assert denied["job_state"]["job"]["status"] == "failed"
    assert denied["job_state"]["cases"][0]["steps"][-1]["status"] == "failed"
    assert len(fake.posts) == 2


def test_stopped_checkpoint_fails_the_step(client, studio):
    fake = studio("stop")
    _start(client, "job-rules-4", count=1, rule_snapshot=SNAPSHOT)

    state = _sync(client, "job-rules-4")["job_state"]

    assert state["job"]["status"] == "failed"
    assert state["cases"][0]["status"] == "failed"
    assert len(fake.posts) == 1
    # Nothing waits: a late decision is rejected.
    assert _resume(client, fake, "job-rules-4", state["cases"][0])["type"] == "rule.checkpoint.rejected"


def test_refresh_request_asks_studio_to_sync_the_job(monkeypatch):
    """The event Studio turns into a job.sync, which runs the held checkpoints."""
    import asyncio

    posts = []

    async def post(url, *, headers, json):
        posts.append({"url": url, "headers": headers, "body": json})
        return SimpleNamespace(raise_for_status=lambda: None)

    account = SimpleNamespace(
        url_event="https://studio.example/w/odm/api/v1/ctrl-events/",
        api_headers={"Authorization": "Api-Key test"},
        workspace_id="odm",
    )
    monkeypatch.setattr(agent_rules, "account", account)
    monkeypatch.setattr(agent_rules, "REFRESH_DELAY_SECONDS", 0)
    monkeypatch.setattr(agent_rules._refresh_client, "post", post)

    asyncio.run(agent_rules._request_refresh("job-rules-9"))

    assert posts == [
        {
            "url": "https://studio.example/w/odm/api/v1/ctrl-events/",
            "headers": {"Authorization": "Api-Key test"},
            "body": {
                "source": {"job": "job-rules-9"},
                "workspace": "odm",
                "event_type": "supervaizer.v2.job.refresh_requested",
                "object_type": "job",
                "details": {"reason": "rule_checkpoints"},
            },
        }
    ]
