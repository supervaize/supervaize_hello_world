# supervaize_hello_world/tests/test_hitl.py
"""The simple agent's start form: random case content and an optional human-in-the-loop case."""
from tests.test_data_resource_e2e import _a2a_request, _action_payload


def _invoke(client, agent_slug, case_id=None, step_id=None, **payload):
    params = _action_payload(agent_slug, **payload)
    params.update(case_id=case_id, step_id=step_id)
    request = _a2a_request(method="supervaizer/action.invoke", params=params)
    return client.post("/a2a", json=request).json()["result"]["effects"][0]


def test_start_creates_cases_with_random_content(client):
    from supervaizer_control import simple_agent

    effect = _invoke(client, simple_agent.slug, action="job.start", action_input={"count": 2}, job_id="job-rc-1")

    assert effect["type"] == "job.started"
    assert effect["status"] == "completed"
    cases = effect["job_state"]["cases"]
    assert len(cases) == 2
    for case in cases:
        assert case["status"] == "completed"
        assert case["metadata"]["message"].startswith("Hello, ")
        assert case["metadata"]["name"] in case["title"]


def test_start_with_human_in_the_loop_adds_an_awaiting_case(client):
    from supervaizer_control import simple_agent

    effect = _invoke(
        client,
        simple_agent.slug,
        action="job.start",
        action_input={"count": 2, "add_human_in_the_loop": True},
        job_id="job-hitl-2",
    )

    assert effect["status"] == "awaiting"
    cases = effect["job_state"]["cases"]
    assert len(cases) == 3
    review = cases[-1]
    step = review["steps"][0]
    assert review["status"] == "awaiting"
    assert step["awaiting"]["reason"] == "human_input"
    assert step["awaiting"]["surface"] == "case.step.awaiting"
    assert step["awaiting"]["action"] == "step.awaiting.submit"

    submitted = _invoke(
        client,
        simple_agent.slug,
        action="step.awaiting.submit",
        action_input={"approved": True, "comment": "Looks good"},
        job_id="job-hitl-2",
        case_id=review["id"],
        step_id=step["id"],
    )

    assert submitted["type"] == "step.awaiting.submitted"
    state = submitted["job_state"]
    assert state["job"]["status"] == "completed"
    assert all(case["status"] == "completed" for case in state["cases"])
    assert "awaiting" not in state["cases"][-1]["steps"][0]
    assert state["cases"][-1]["metadata"]["comment"] == "Looks good"


def test_start_form_offers_the_human_in_the_loop_flag(client):
    from supervaizer_control import simple_agent
    from tests.test_data_resource_e2e import _surface_payload

    request = _a2a_request(method="supervaizer/surface.load", params=_surface_payload(simple_agent.slug, surface="job.start"))
    document = client.post("/a2a", json=request).json()["result"]["document"]

    fields = {field["id"]: field for field in document["fields"]}
    assert fields["add_human_in_the_loop"]["type"] == "boolean"
    assert fields["add_human_in_the_loop"]["default"] is False
