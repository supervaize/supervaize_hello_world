# supervaize_hello_world/tests/test_hitl.py
"""The simple agent's start form: random case content and an optional human-in-the-loop case."""
from tests.test_data_resource_e2e import _a2a_request, _action_payload


def _invoke(client, agent_slug, case_id=None, step_id=None, **payload):
    params = _action_payload(agent_slug, **payload)
    params.update(case_id=case_id, step_id=step_id)
    request = _a2a_request(method="supervaizer/action.invoke", params=params)
    result = client.post("/a2a", json=request).json()["result"]
    effect = result["effects"][0]
    # Studio reads job_state from the result only; one inside the effect is lost.
    assert "job_state" not in effect
    return {**effect, "job_state": result["job_state"]} if "job_state" in result else effect


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
    step = review["steps"][-1]
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
    assert "awaiting" not in state["cases"][-1]["steps"][-1]
    assert state["cases"][-1]["metadata"]["comment"] == "Looks good"


def test_start_form_offers_the_human_in_the_loop_flag(client):
    from supervaizer_control import simple_agent
    from tests.test_data_resource_e2e import _surface_payload

    request = _a2a_request(method="supervaizer/surface.load", params=_surface_payload(simple_agent.slug, surface="job.start"))
    document = client.post("/a2a", json=request).json()["result"]["document"]

    fields = {field["id"]: field for field in document["fields"]}
    assert fields["add_human_in_the_loop"]["type"] == "boolean"
    assert fields["add_human_in_the_loop"]["default"] is False


def test_stop_is_declared_and_drops_the_job(client):
    """Studio's Stop button needs job.stop in the registration and an ok answer."""
    import agent_v2
    from supervaizer_control import simple_agent

    actions = [action.id for action in agent_v2.build_simple_agent_v2_registration("1.0").capabilities.actions]
    assert "job.stop" in actions
    _invoke(client, simple_agent.slug, action="job.start", action_input={"count": 1}, job_id="job-stop-1")

    effect = _invoke(client, simple_agent.slug, action="job.stop", job_id="job-stop-1")

    assert effect["type"] == "job.stopped"
    assert "job-stop-1" not in agent_v2._jobs


def test_every_step_costs_ten_cents(client, human_loop_client):
    """Studio adds step costs up into the case and job cost."""
    from supervaizer_control import human_loop_agent, simple_agent

    simple = _invoke(
        client, simple_agent.slug, action="job.start", action_input={"count": 2, "add_human_in_the_loop": True}, job_id="job-cost-1"
    )
    human = _invoke(
        human_loop_client, human_loop_agent.slug, action="job.start", action_input={"case_count": 1}, job_id="job-cost-2"
    )

    steps = [step for state in (simple, human) for case in state["job_state"]["cases"] for step in case["steps"]]
    assert len(steps) == 8  # Start plus one more step per case
    assert all(step["cost"] == 0.1 for step in steps)
    # Studio takes the job cost from the snapshot: 3 cases x 2 steps, and 1 case x 2 steps.
    assert simple["job_state"]["job"]["information"]["cost"] == {"total_cost": 0.6}
    assert human["job_state"]["job"]["information"]["cost"] == {"total_cost": 0.2}


def test_each_hello_case_delivers_a_greeting_card(client):
    """Start, then a step whose output Studio fetches with artifact.get."""
    from supervaizer_control import simple_agent

    started = _invoke(client, simple_agent.slug, action="job.start", action_input={"count": 1}, job_id="job-card-1")
    case = started["job_state"]["cases"][0]
    assert [step["title"] for step in case["steps"]] == ["Start", "Deliver greeting card"]
    card = case["steps"][-1]["outputs"][0]

    loaded = _invoke(client, simple_agent.slug, action="artifact.get", action_input={"artifact": card}, job_id="job-card-1")

    assert loaded["type"] == "artifact.loaded"
    assert loaded["artifact"]["content"] == f"# Greeting card\n\n{case['metadata']['message']}\n"
