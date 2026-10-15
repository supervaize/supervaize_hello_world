# supervaize_hello_world/tests/test_main.py
"""main.py is the Vercel entrypoint; importing it must not break on an SDK upgrade."""
from supervaizer.__version__ import VERSION

from supervaizer_control import AGENT_VERSION


def test_main_imports_and_serves_context(client):
    import main

    assert main.app is client.app
    resp = client.get("/api/context")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == VERSION
    assert body["agent_version"] == AGENT_VERSION
    assert "\n" not in body["base"]
