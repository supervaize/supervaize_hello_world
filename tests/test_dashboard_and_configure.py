# supervaize_hello_world/tests/test_dashboard_and_configure.py
"""Shared dashboard (mission.analytics + dataset query) and the configure form."""
from tests.test_data_resource_e2e import _a2a_request, _action_payload, _surface_payload


def _load(client, slug, surface, **surface_input):
    params = _surface_payload(slug, surface=surface)
    params["input"] = surface_input
    return client.post("/a2a", json=_a2a_request(method="supervaizer/surface.load", params=params)).json()["result"]


def _invoke(client, slug, action, action_input=None, job_id=None):
    params = _action_payload(slug, action=action, action_input=action_input, job_id=job_id)
    return client.post("/a2a", json=_a2a_request(method="supervaizer/action.invoke", params=params)).json()["result"]


def test_registration_declares_dataset_and_analytics_surface():
    from supervaizer_control import simple_agent

    registration = simple_agent.supervaizer_v2_registration
    assert "mission.analytics" in registration.capabilities.surfaces
    assert "mission.agent.dataset.hello_cases" in registration.capabilities.surfaces
    query = next(a for a in registration.capabilities.actions if a.id == "dataset.hello_cases.query")
    assert query.mutating is False
    assert query.scope == "mission"


def test_analytics_surface_is_a_dashboard_with_metrics_and_widgets(client):
    from supervaizer_control import simple_agent

    document = _load(client, simple_agent.slug, "mission.analytics")["document"]

    assert document["type"] == "Dashboard"
    dataset = document["datasets"][0]
    assert dataset["id"] == "hello_cases"
    assert {metric["reducer"] for metric in dataset["metrics"]} == {"row_count", "distinct_count", "ratio"}
    assert {widget["visualization"]["type"] for widget in document["widgets"]} == {"vega-lite", "table"}
    assert document["controls"][0]["id"] == "status"


def test_dataset_query_returns_the_cases_started_so_far(client):
    from supervaizer_control import simple_agent

    _invoke(client, simple_agent.slug, "job.start", {"count": 2, "add_human_in_the_loop": True}, job_id="job-dash-1")

    queried = _invoke(client, simple_agent.slug, "dataset.hello_cases.query")["effects"][0]
    assert queried["type"] == "dataset.queried"
    assert queried["dataset"] == "hello_cases"
    rows = [row for row in queried["rows"] if row["job_id"] == "job-dash-1"]
    assert len(rows) == 3
    assert {row["status"] for row in rows} == {"completed", "awaiting"}
    assert sum(row["completed"] for row in rows) == 2

    awaiting = _invoke(client, simple_agent.slug, "dataset.hello_cases.query", {"status": "awaiting"})["effects"][0]
    assert all(row["status"] == "awaiting" for row in awaiting["rows"])
    assert any(row["job_id"] == "job-dash-1" for row in awaiting["rows"])


def test_configure_form_fields_shape_the_case_messages(client):
    from supervaizer_control import simple_agent

    document = _load(client, simple_agent.slug, "job.configurator", job_id="job-cfg-2")
    fields = {f["id"]: f for f in document["document"]["sections"][0]["component"]["data"]["fields"]}
    assert fields["greeting"]["type"] == "text"
    assert fields["signature"]["type"] == "text"
    assert fields["shout"]["type"] == "boolean"

    saved = _invoke(
        client,
        simple_agent.slug,
        "job.configure",
        {"revision": "0", "value": {"greeting": "Hi", "signature": "The team", "shout": True}},
        job_id="job-cfg-2",
    )
    assert saved["status"] == "ok"

    started = _invoke(client, simple_agent.slug, "job.start", {"count": 1}, job_id="job-cfg-2")
    message = started["job_state"]["cases"][0]["metadata"]["message"]
    assert message.startswith("HI, ")
    assert message.endswith("THE TEAM")
