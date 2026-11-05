"""Shared dashboard example: a mission-level dataset with KPI metrics and a chart.

Studio opens the ``mission.analytics`` surface from the mission page, and shows
the ``job.analytics`` surface as a Job Analytics section on each job page. The
agent answers both with the same builder; the job dashboard scopes its dataset
to the job. The agent answers with a ``Dashboard`` document that declares datasets (with metric
reducers Studio turns into KPI cards), controls and widgets. Studio then calls
``dataset.<id>.query`` for each dataset and renders tables and Vega-Lite charts
from the returned rows.
"""

from __future__ import annotations

from typing import Any

ANALYTICS_SURFACE = "mission.analytics"
JOB_ANALYTICS_SURFACE = "job.analytics"
DATASET_ID = "hello_cases"
DATASET_QUERY_ACTION = f"dataset.{DATASET_ID}.query"
COLUMNS = ["job_id", "title", "name", "city", "status", "message"]


def dataset_definition() -> dict[str, Any]:
    """Registration entry; the SDK derives the query action and a dataset surface from it."""
    return {
        "id": DATASET_ID,
        "label": "Hello cases",
        # Workspace scope (the default): Studio runs a dataset query from a job page
        # only for a workspace-scoped dataset. The dashboards scope the rows themselves.
        "scope": "workspace",
        "auto_surface": True,
        "display": {"columns": COLUMNS},
    }


def analytics_document(surface_input: dict[str, Any], job_id: str | None = None) -> dict[str, Any]:
    """The shared dashboard: one dataset, three KPI cards, a status filter, a chart and a table.

    With ``job_id`` it is the job dashboard: Studio sends ``job_ref`` back with every dataset query.
    """
    status = str(surface_input.get("status") or "all")
    dataset_input = {"status": status}
    if job_id:
        dataset_input["job_ref"] = job_id
    return {
        "type": "Dashboard",
        "id": f"hello_world.{'job' if job_id else 'mission'}.analytics",
        "title": "Job analytics" if job_id else "Hello World analytics",
        "datasets": [
            {
                "id": DATASET_ID,
                "label": "Hello cases",
                "input": dataset_input,
                "display": {"columns": COLUMNS},
                "metrics": [
                    {"id": "cases", "label": "Cases", "reducer": "row_count"},
                    {"id": "cities", "label": "Cities", "reducer": "distinct_count", "field": "city"},
                    {
                        "id": "completed",
                        "label": "Completed",
                        "reducer": "ratio",
                        "numerator_field": "completed",
                        "denominator_field": "total",
                    },
                ],
            }
        ],
        "controls": [
            {
                "id": "status",
                "label": "Status",
                "type": "segmented",
                "default": status,
                "options": [
                    {"label": "All", "value": "all"},
                    {"label": "Completed", "value": "completed"},
                    {"label": "Awaiting", "value": "awaiting"},
                ],
            }
        ],
        "widgets": [
            {
                "id": "cases_by_city",
                "title": "Cases by city",
                "data": {"mode": "ref", "datasetId": DATASET_ID, "input": dataset_input},
                "visualization": {
                    "type": "vega-lite",
                    "spec": {
                        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                        "mark": "bar",
                        "encoding": {
                            "x": {"field": "city", "type": "nominal", "title": "City"},
                            "y": {"aggregate": "count", "type": "quantitative", "title": "Cases"},
                            "color": {"field": "status", "type": "nominal", "title": "Status"},
                        },
                    },
                },
            },
            {
                "id": "cases_table",
                "title": "Cases",
                "data": {"mode": "ref", "datasetId": DATASET_ID, "input": dataset_input},
                "visualization": {"type": "table"},
            },
        ],
        "state": {"status": status},
    }


def query_dataset(jobs: dict[str, dict[str, Any]], action_input: dict[str, Any]) -> dict[str, Any]:
    """One row per case of the jobs this controller started, filtered by job and by the status control."""
    status = str(action_input.get("status") or "all")
    job_ref = action_input.get("job_ref")
    rows = [
        {
            "job_id": job_id,
            "case_id": case["id"],
            "title": case.get("title"),
            "name": case.get("metadata", {}).get("name"),
            "city": case.get("metadata", {}).get("city"),
            "status": case.get("status"),
            "message": case.get("metadata", {}).get("message"),
            "completed": 1 if case.get("status") == "completed" else 0,
            "total": 1,
        }
        for job_id, job_state in jobs.items()
        if not job_ref or job_id == job_ref
        for case in job_state.get("cases", [])
        if status == "all" or case.get("status") == status
    ]
    return {
        "status": "ok",
        "effects": [{"type": "dataset.queried", "dataset": DATASET_ID, "count": len(rows), "rows": rows}],
    }
