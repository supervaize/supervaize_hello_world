# supervaize_hello_world/tests/test_data_resource_e2e.py
"""E2E tests for the contacts DataResource via FastAPI TestClient.

These tests verify the full data resource lifecycle:
list → get → create → update → delete → import
All without a real network — TestClient exercises the actual route handlers.
"""

BASE = "/api/agents/hello-world-ai-agent/data/contacts"


def test_list_contacts_returns_two_seeded_contacts(client):
    """GET /data/contacts/ returns the two seeded contacts."""
    resp = client.get(f"{BASE}/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    emails = {c["email"] for c in data}
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails


def test_get_contact_by_id(client):
    """GET /data/contacts/{id} returns the correct contact."""
    resp = client.get(f"{BASE}/c1")
    assert resp.status_code == 200
    contact = resp.json()
    assert contact["id"] == "c1"
    assert contact["first_name"] == "Alice"


def test_get_contact_not_found(client):
    """GET /data/contacts/{id} returns 404 for unknown ID."""
    resp = client.get(f"{BASE}/does-not-exist")
    assert resp.status_code == 404


def test_create_contact(client):
    """POST /data/contacts/ creates a new contact and returns it with an id."""
    payload = {
        "first_name": "Carol",
        "last_name": "White",
        "email": "carol@example.com",
    }
    resp = client.post(f"{BASE}/", json=payload)
    assert resp.status_code == 201
    created = resp.json()
    assert "id" in created
    assert created["first_name"] == "Carol"
    assert created["email"] == "carol@example.com"


def test_create_contact_appears_in_list(client):
    """Contact created via POST appears in subsequent GET list (total = 3)."""
    client.post(f"{BASE}/", json={"first_name": "Dave", "email": "dave@example.com"})
    resp = client.get(f"{BASE}/")
    contacts = resp.json()
    assert len(contacts) == 3  # 2 seeded + 1 created
    emails = {c["email"] for c in contacts}
    assert "dave@example.com" in emails


def test_update_contact(client):
    """PUT /data/contacts/{id} merges fields — unchanged fields are preserved."""
    resp = client.put(f"{BASE}/c1", json={"first_name": "Alicia", "city": "Lyon"})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["first_name"] == "Alicia"
    assert updated["city"] == "Lyon"
    assert updated["id"] == "c1"  # id must not change
    assert updated["email"] == "alice@example.com"  # unchanged fields preserved


def test_update_contact_not_found(client):
    """PUT /data/contacts/{id} returns 404 for unknown ID."""
    resp = client.put(f"{BASE}/does-not-exist", json={"first_name": "Ghost"})
    assert resp.status_code == 404


def test_delete_contact(client):
    """DELETE /data/contacts/{id} removes the contact."""
    resp = client.delete(f"{BASE}/c2")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    # Confirm it is gone
    assert client.get(f"{BASE}/c2").status_code == 404


def test_delete_contact_not_found(client):
    """DELETE /data/contacts/{id} returns 404 for unknown ID."""
    resp = client.delete(f"{BASE}/no-such-id")
    assert resp.status_code == 404


def test_bulk_import(client):
    """POST /data/contacts/import/ inserts multiple contacts."""
    records = [
        {"first_name": "Eve", "email": "eve@example.com"},
        {"first_name": "Frank", "email": "frank@example.com"},
    ]
    resp = client.post(f"{BASE}/import/", json=records)
    assert resp.status_code == 200
    result = resp.json()
    assert result["created"] == 2

    # Verify they appear in list (2 seeded + 2 imported = 4 total)
    list_resp = client.get(f"{BASE}/")
    all_contacts = list_resp.json()
    assert len(all_contacts) == 4
    emails = {c["email"] for c in all_contacts}
    assert "eve@example.com" in emails
    assert "frank@example.com" in emails


def test_unauthenticated_request_rejected():
    """Requests without API key are rejected."""
    from fastapi.testclient import TestClient

    from supervaizer_control import sv_server

    unauth = TestClient(sv_server.app)
    resp = unauth.get(f"{BASE}/")
    assert resp.status_code in (401, 403)


def test_agent_registration_info_includes_contacts_resource():
    """Agent.registration_info declares contacts in data_resources."""
    from supervaizer_control import simple_agent

    info = simple_agent.registration_info
    assert "data_resources" in info
    names = [r["name"] for r in info["data_resources"]]
    assert "contacts" in names

    contacts_info = next(r for r in info["data_resources"] if r["name"] == "contacts")
    assert contacts_info["importable"] is True
    assert contacts_info["read_only"] is False
    assert contacts_info["operations"]["create"] is True
    assert contacts_info["operations"]["import"] is True

    email_field = next(field for field in contacts_info["fields"] if field["name"] == "email")
    assert email_field["sensitive"] is True

    v2 = info["supervaizer_v2"]
    assert v2["versions"]["a2ui_version"] == "v0.8"
    assert "job.start" in v2["capabilities"]["surfaces"]
    assert "resource.contacts.list" in [a["id"] for a in v2["capabilities"]["actions"]]
    assert v2["resources"][0]["id"] == "contacts"


def test_controller_contract_endpoint_advertises_required_templates(client):
    """GET /api/supervaizer/contract publishes the SDK controller contract."""
    from supervaizer.contracts import ControllerEndpoint

    resp = client.get("/api/supervaizer/contract")
    assert resp.status_code == 200
    contract = resp.json()

    assert contract["controller_contract_version"] == "1.0"
    assert contract["api_base_path"] == "/api"
    endpoints = contract["endpoints"]
    for endpoint in [
        ControllerEndpoint.POST_AGENT_JOB_START,
        ControllerEndpoint.POST_AGENT_CASE_UPDATE,
        ControllerEndpoint.DATA_RESOURCE,
        ControllerEndpoint.DATA_RESOURCE_ITEM,
        ControllerEndpoint.DATA_RESOURCE_IMPORT,
        ControllerEndpoint.HEALTH_CHECK,
        ControllerEndpoint.CONTROLLER_CONTRACT,
    ]:
        assert endpoint.value in endpoints


def test_a2a_agent_card_includes_v2_registration(client):
    """The public Agent Card advertises the Supervaizer v2 extension."""
    from supervaizer_control import simple_agent

    response = client.get(
        f"/.well-known/agents/v{simple_agent.version}/{simple_agent.slug}_agent.json"
    )

    assert response.status_code == 200
    v2 = response.json()["supervaizer"]["v2"]
    assert v2["agent"]["slug"] == simple_agent.slug
    assert v2["a2a"]["controller_url"] == "/a2a"
    assert v2["a2a"]["transport"]["push_notifications"] is False


def test_a2a_loads_job_start_surface(client):
    """Studio can load the v2 job.start A2UI surface through A2A JSON-RPC."""
    from supervaizer_control import simple_agent

    response = client.post(
        "/a2a",
        json=_a2a_request(
            method="supervaizer/surface.load",
            params=_surface_payload(simple_agent.slug, surface="job.start"),
        ),
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["surface"] == "job.start"
    assert result["document"]["type"] == "Form"
    assert result["document"]["submit"]["action"] == "job.start"


def test_a2a_lists_contacts_resource(client):
    """Studio can list contacts through the v2 typed resource action."""
    from supervaizer_control import simple_agent

    response = client.post(
        "/a2a",
        json=_a2a_request(
            method="supervaizer/action.invoke",
            params=_action_payload(simple_agent.slug, action="resource.contacts.list"),
        ),
    )

    assert response.status_code == 200
    effect = response.json()["result"]["effects"][0]
    assert effect["type"] == "resource.listed"
    assert effect["resource"] == "contacts"
    assert effect["count"] == 2


def test_a2a_human_loop_start_returns_awaiting_step(human_loop_client):
    """The v2 HITL demo exposes awaiting state instead of supervaizer_form HTML."""
    from supervaizer_control import human_loop_agent

    response = human_loop_client.post(
        "/a2a",
        json=_a2a_request(
            method="supervaizer/action.invoke",
            params=_action_payload(
                human_loop_agent.slug,
                action="job.start",
                action_input={"case_count": 1},
                job_id="job-hitl-1",
            ),
        ),
    )

    assert response.status_code == 200
    effect = response.json()["result"]["effects"][0]
    step = effect["job_state"]["cases"][0]["steps"][0]
    assert effect["type"] == "job.started"
    assert step["status"] == "awaiting"
    assert step["awaiting"]["reason"] == "human_input"
    assert step["awaiting"]["surface"] == "case.step.awaiting"


def _a2a_request(method: str, params: dict) -> dict:
    return {"jsonrpc": "2.0", "id": "rpc-test", "method": method, "params": params}


def _surface_payload(agent_slug: str, *, surface: str) -> dict:
    return {
        "request_id": "request-1",
        "actor": {"user_id": "user-1"},
        "workspace": {"id": "workspace-1", "slug": "workspace"},
        "mission_id": "mission-1",
        "agent_slug": agent_slug,
        "surface": surface,
        "input": {},
        "draft_session_id": "draft-1",
    }


def _action_payload(
    agent_slug: str,
    *,
    action: str,
    action_input: dict | None = None,
    job_id: str | None = None,
) -> dict:
    payload = _surface_payload(agent_slug, surface="job.start")
    payload["action"] = action
    payload["input"] = action_input or {}
    payload["job_id"] = job_id
    return payload
