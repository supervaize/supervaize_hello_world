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


# Keys Studio's parser refuses anywhere in a Configurator document, compared
# without punctuation and case (so `job_id` is refused as `jobid`).
UNSAFE_KEYS = {
    "html", "script", "iframe", "src", "style", "css", "import", "remoteimport", "expression",
    "expressionlanguage", "targetid", "jobid", "missionid", "caseid", "stepid",
}  # fmt: skip


def _keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield "".join(ch for ch in key if ch.isalnum()).lower()
            yield from _keys(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def test_configurator_sections_readiness_and_primary_action(client, monkeypatch):
    from supervaizer_control import simple_agent

    monkeypatch.setitem(globals(), "JOB_ID", "job-cfg-3")
    slug = simple_agent.slug
    document = _load(client, slug)

    # Schema 2 adds the read-only Table; every binding names a declared action.
    assert document["schema_version"] == "2"
    assert [s["component"]["type"] for s in document["sections"]] == ["Form", "Review", "Table"]
    assert not UNSAFE_KEYS & set(_keys(document))
    declared = {action.id for action in simple_agent.supervaizer_v2_registration.capabilities.actions}
    assert document["primary_action"]["binding"]["action_id"] in declared

    # No signature yet: the checklist blocks the primary action, and the agent enforces it.
    assert [item["status"] for item in document["readiness"]] == ["ok", "blocked"]
    assert document["primary_action"]["status"] == "disabled"
    refused = _invoke(client, slug, "job.greet", {"revision": document["revision"]})
    assert refused["effects"][0]["type"] == "job.greet.failed"

    _invoke(client, slug, "job.start", {"count": 2})
    value = {"greeting": "Hi", "signature": "The team"}
    saved = _invoke(client, slug, "job.configure", {"revision": document["revision"], "value": value})
    assert "state_label" not in saved["job_state"]["job"]["display"]

    document = _load(client, slug)
    assert document["primary_action"]["status"] == "enabled"
    stale = _invoke(client, slug, "job.greet", {"revision": "0"})
    assert stale["effects"][0]["type"] == "configurator.conflict"
    greeted = _invoke(client, slug, "job.greet", {"revision": document["revision"]})
    assert len(greeted["job_state"]["cases"]) == 2
    assert greeted["job_state"]["cases"][0]["metadata"]["message"].endswith("The team")

    # The sample card opens through the job's read-only artifact.get.
    artifact = document["sections"][2]["component"]["data"]["rows"][1]["link"]["artifact"]
    loaded = _invoke(client, slug, "artifact.get", {"artifact": artifact, "artifact_id": artifact["id"]})
    assert "Hi, Ada from Paris! The team" in loaded["effects"][0]["artifact"]["content"]


def test_send_greetings_keeps_the_case_that_waits_for_a_person(client, monkeypatch):
    from supervaizer_control import simple_agent

    monkeypatch.setitem(globals(), "JOB_ID", "job-cfg-5")
    slug = simple_agent.slug
    started = _invoke(client, slug, "job.start", {"count": 2, "add_human_in_the_loop": True})
    assert started["job_state"]["job"]["display"]["state_label"] == "Draft — setup incomplete"

    value = {"greeting": "Hi", "signature": "The team"}
    _invoke(client, slug, "job.configure", {"revision": "0", "value": value})
    greeted = _invoke(client, slug, "job.greet", {"revision": "1"})["job_state"]

    assert [case["status"] for case in greeted["cases"]] == ["completed", "completed", "awaiting"]
    assert greeted["job"]["status"] == "awaiting"
    assert greeted["job"]["information"]["cost"]["total_cost"] == 0.6

    # A completed job never keeps the draft label, with or without a signature.
    other = _action_payload(slug, action="job.start", action_input={"count": 1}, job_id="job-cfg-6")
    request = _a2a_request(method="supervaizer/action.invoke", params=other)
    completed = client.post("/a2a", json=request).json()["result"]["job_state"]["job"]
    assert completed["status"] == "completed"
    assert "state_label" not in completed["display"]


def test_configurator_negotiates_the_schema_version(client):
    from agent_configurator import configurator_document

    schema_1 = configurator_document("job-cfg-4", {"supported_schema_versions": ["1"]})
    assert [s["component"]["type"] for s in schema_1["sections"]] == ["Form", "Review"]
    assert configurator_document("job-cfg-4", {"supported_schema_versions": ["9"]})["type"] == "ConfiguratorError"
