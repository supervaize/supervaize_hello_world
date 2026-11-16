# supervaize_hello_world/tests/test_sdk_1_11_features.py
"""SDK 1.9 to 1.11 features: introduction, full description, billing, guided setup."""

import asyncio
from decimal import Decimal

import agent_billing
from tests.test_dashboard_and_configure import _invoke


def test_registration_carries_profile_billing_and_setup_plan():
    from supervaizer_control import simple_agent

    info = simple_agent.registration_info
    assert info["introduction"]["tagline"]
    assert info["full_description"]["format"] == "markdown"
    assert info["billing_catalog"] == [
        {"sku": "hello_message", "unit": "message", "description": "One hello greeting"}
    ]
    registration = simple_agent.supervaizer_v2_registration
    plan = registration.job_policy.setup.plan
    assert plan.steps[0].help_actions == ["count.suggest"]
    actions = {action.id: action for action in registration.capabilities.actions}
    assert actions["count.suggest"].kind == "help"
    assert actions["job.test"].dry_run is True


def test_preview_returns_a_cost_range_for_the_chosen_count(client):
    from supervaizer_control import simple_agent

    result = _invoke(
        client,
        simple_agent.slug,
        "job.start.preview",
        {"count": 4, "add_human_in_the_loop": True},
    )
    estimate = result["setup_plan"]["cost_estimate"]
    assert (estimate["min"], estimate["max"]) == (0.4, 0.5)


def test_help_action_proposes_one_hello_per_contact(client):
    from supervaizer_control import simple_agent

    draft = _invoke(
        client, simple_agent.slug, "count.suggest", {"field": "count", "values": {}}
    )["draft"]
    assert draft == {
        "field": "count",
        "value": 2,
        "suggestions": [draft["suggestions"][0]],
    }


def test_test_run_creates_no_case(client):
    from supervaizer_control import simple_agent

    result = _invoke(client, simple_agent.slug, "job.test", job_id="job-dry-1")
    assert result["dry_run"]["deletable"] is True
    assert "job_state" not in result


def test_job_start_reports_one_record_per_job(client, monkeypatch):
    from supervaizer_control import simple_agent

    calls = []
    monkeypatch.setattr(
        agent_billing, "report_hellos", lambda **kwargs: calls.append(kwargs)
    )
    _invoke(client, simple_agent.slug, "job.start", {"count": 3}, job_id="job-bill-1")
    assert calls == [
        {
            "agent_slug": simple_agent.slug,
            "workspace_id": "workspace-1",
            "job_id": "job-bill-1",
            "count": 3,
        }
    ]


def test_report_sends_the_record_with_a_stable_key(monkeypatch):
    sent = []

    class _Account:
        async def report_consumption(self, records, *, agent_slug, workspace_id=None):
            sent.append((records, agent_slug, workspace_id))
            return []

    monkeypatch.setattr(agent_billing, "account", _Account())

    async def run():
        agent_billing.report_hellos(
            agent_slug="hello", workspace_id="ws", job_id="job-1", count=2
        )
        await asyncio.gather(*agent_billing._pending)

    asyncio.run(run())
    ((records, slug, workspace),) = sent
    assert (slug, workspace) == ("hello", "ws")
    assert records[0].quantity == Decimal(2)
    assert records[0].idempotency_key == "job-1:hello_message"
