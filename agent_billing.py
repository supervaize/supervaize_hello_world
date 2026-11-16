"""Billable consumption: one SKU, reported to Studio for each greeting a job delivers."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from loguru import logger
from supervaizer import Account, BillableConsumption, BillingCatalogItem

SKU = "hello_message"
# No price here: the owner workspace prices the SKU in Studio.
BILLING_CATALOG = [
    BillingCatalogItem(sku=SKU, unit="message", description="One hello greeting")
]

# Set by supervaizer_control; None turns reporting off.
account: Account | None = None
# Keeps background reports alive until they finish.
_pending: set[asyncio.Task] = set()


def report_hellos(
    *, agent_slug: str, workspace_id: str | None, job_id: str, count: int
) -> None:
    """Report `count` greetings for a job in the background, so job.start does not wait on Studio."""
    if account is None or count <= 0:
        return
    record = BillableConsumption(
        sku=SKU,
        quantity=Decimal(count),
        unit="message",
        job_id=job_id,
        # One record per job: a resend after a lost response answers "duplicate".
        idempotency_key=f"{job_id}:{SKU}",
        occurred_at=datetime.now(UTC),
        description=f"{count} hello greeting(s)",
    )
    task = asyncio.create_task(
        _send(record, agent_slug=agent_slug, workspace_id=workspace_id)
    )
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def _send(
    record: BillableConsumption, *, agent_slug: str, workspace_id: str | None
) -> None:
    try:
        receipts = await account.report_consumption(
            [record], agent_slug=agent_slug, workspace_id=workspace_id
        )
    except httpx.HTTPError as error:
        # ponytail: no outbox; a lost record is not resent. Add one when billing matters.
        logger.warning(
            f"[Billing] Consumption report for job {record.job_id} failed: {error}"
        )
        return
    for receipt in receipts:
        if receipt.status == "rejected":
            logger.warning(
                f"[Billing] Studio rejected {receipt.idempotency_key}: {receipt.reason}"
            )


def workspace_id(data: dict[str, Any]) -> str | None:
    """The workspace that runs the job; None falls back to the account's workspace.

    Studio routes /w/<workspace>/ by slug: the request's workspace `id` is the
    database key and answers 404.
    """
    workspace = data.get("workspace")
    return workspace.get("slug") if isinstance(workspace, dict) else None
