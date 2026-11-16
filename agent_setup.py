"""Guided setup for the Hello World agent: setup plan, cost estimate, help action and test run."""

from typing import Any

from supervaizer import (
    V2ActionDefinition,
    V2CostEstimate,
    V2SetupFieldDefinition,
    V2SetupPlan,
    V2SetupStep,
)

from agent_configurator import job_config
from agent_configurator import message as greeting_message

MAX_COUNT = 100
# Dollars per step; Studio adds step costs up into the case and job cost.
STEP_COST = 0.1

SUGGEST_COUNT_ACTION = V2ActionDefinition(
    id="count.suggest",
    kind="help",
    mutating=False,
    scope="mission",
    target_field="count",
)
TEST_ACTION = V2ActionDefinition(
    id="job.test", dry_run=True, mutating=False, scope="mission", label="Test run"
)


def cost_estimate(count: int | None = None, with_human: bool = False) -> V2CostEstimate:
    """A range: Studio never shows a single number. One more step when a human reviews."""
    if count is None:
        return V2CostEstimate(
            status="estimated",
            unit="USD",
            min=STEP_COST,
            max=MAX_COUNT * STEP_COST,
            basis=f"1 to {MAX_COUNT} hellos at {STEP_COST:.2f} USD each",
        )
    low = round(count * STEP_COST, 2)
    high = round(low + (STEP_COST if with_human else 0), 2)
    return V2CostEstimate(
        status="estimated",
        unit="USD",
        min=low,
        max=high,
        basis=f"{count} hello(s) at {STEP_COST:.2f} USD each"
        + (", plus one review step" if with_human else ""),
    )


SETUP_PLAN = V2SetupPlan(
    steps=[
        V2SetupStep(
            id="greeting",
            title="Greeting",
            description="Choose how many hellos the job says.",
            fields=[
                V2SetupFieldDefinition(
                    id="count",
                    label="How many times to say hello",
                    type="integer",
                    required=True,
                    default=3,
                    description="Each hello is one case with a greeting card.",
                    validation={
                        "min": 1,
                        "max": MAX_COUNT,
                        "message": f"Say hello 1 to {MAX_COUNT} times",
                    },
                ),
                V2SetupFieldDefinition(
                    id="add_human_in_the_loop",
                    label="Add human in the loop",
                    type="boolean",
                    default=False,
                    description="Adds one case that waits for a human approval.",
                ),
            ],
            help_actions=[SUGGEST_COUNT_ACTION.id],
        )
    ],
    cost_estimate=cost_estimate(),
)


def suggest_count(values: dict[str, Any], contact_count: int) -> dict[str, Any]:
    """Help action result: propose one hello per contact. Studio shows it as an editable draft."""
    count = max(1, min(contact_count, MAX_COUNT))
    return {
        "status": "ok",
        "effects": [{"type": "draft.proposed", "field": "count"}],
        "draft": {
            "field": "count",
            "value": count,
            "suggestions": [
                {
                    "message": f"One hello for each of your {contact_count} contact(s).",
                    "severity": "info",
                }
            ],
        },
    }


def test_run(job_id: str, values: dict[str, Any]) -> dict[str, Any]:
    """Dry run: preview the first greeting. It creates no case, sends nothing and costs nothing."""
    preview = greeting_message(job_config(job_id), "Ada", "Paris")
    return {
        "status": "ok",
        "effects": [{"type": "job.tested", "message": preview}],
        "dry_run": {
            "deletable": True,
            "cost_incurred": {
                "status": "estimated",
                "unit": "USD",
                "min": 0,
                "max": 0,
                "basis": "A test run is free",
            },
        },
    }
