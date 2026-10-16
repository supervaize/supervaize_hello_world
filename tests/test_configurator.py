# supervaize_hello_world/tests/test_configurator.py
"""Job Configurator: Studio edits a per-job greeting through the A2UI Configurator surface.

Studio renders ``job.configurator`` on the job page. Each section binds its save
to an action that Studio invokes with ``{"revision": ..., "value": {...}}``; a
stale revision gets ``configurator.conflict`` back and Studio reloads.
"""
from tests.test_data_resource_e2e import _a2a_request, _action_payload, _surface_payload

JOB_ID = "job-cfg-1"


def _load(client, slug):
    payload = {**_surface_payload(slug, surface="job.configurator"), "job_id": JOB_ID}
    payload["input"] = {"supported_schema_versions": ["1", "2"]}
    request = _a2a_request(method="supervaizer/surface.load", params=payload)
    return client.post("/a2a", json=request).json()["result"]["document"]


def _invoke(client, slug, action, action_input):
    payload = _action_payload(slug, action=action, action_input=action_input, job_id=JOB_ID)
    request = _a2a_request(method="supervaizer/action.invoke", params=payload)
    return client.post("/a2a", json=request).json()["result"]


def _greeting_field(document):
    return document["sections"][0]["component"]["data"]["fields"][0]


def test_configurator_saves_greeting_and_rejects_stale_revision(client):
    from supervaizer_control import simple_agent

    slug = simple_agent.slug
    document = _load(client, slug)
    assert document["type"] == "Configurator"
    assert document["sections"][0]["component"]["bindings"]["save"]["action_id"] == "job.configure"
    assert _greeting_field(document)["default"] == "Hello"

    revision = document["revision"]
    saved = _invoke(client, slug, "job.configure", {"revision": revision, "value": {"greeting": "Bonjour"}})
    assert saved["effects"][0]["type"] == "job.configured"
    assert _greeting_field(_load(client, slug))["default"] == "Bonjour"

    stale = _invoke(client, slug, "job.configure", {"revision": revision, "value": {"greeting": "Hola"}})
    assert stale["status"] == "error"
    assert stale["effects"][0]["type"] == "configurator.conflict"

    started = _invoke(client, slug, "job.start", {"count": 1})
    case = started["job_state"]["cases"][0]
    assert case["title"].startswith("Bonjour ")
    assert case["metadata"]["message"].startswith("Bonjour, ")
