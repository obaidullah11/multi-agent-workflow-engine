import asyncio
import logging
import uuid

import httpx

from app.core.config import get_settings
from app.db.models import AgentTask, WorkflowRequest, WorkflowStatus
from app.db.session import AsyncSessionLocal
from app.services.ai_agent import AgentExecutionError, TriageAgent
from app.worker.celery_app import celery_app

settings = get_settings()
logger = logging.getLogger(__name__)


@celery_app.task(name="process_workflow_request", bind=True, max_retries=3)
def process_workflow_request(self, workflow_request_id: str) -> None:
    asyncio.run(_process_workflow_request(uuid.UUID(workflow_request_id)))


async def _process_workflow_request(workflow_request_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        workflow_request = await session.get(WorkflowRequest, workflow_request_id)
        if workflow_request is None:
            return

        workflow_request.status = WorkflowStatus.PROCESSING
        await session.commit()

        raw_text = str(workflow_request.raw_payload)
        agent = TriageAgent()

        try:
            extraction, latency_ms = await agent.extract(raw_text)
        except AgentExecutionError as exc:
            workflow_request.status = WorkflowStatus.FAILED
            workflow_request.failure_reason = exc.reason
            session.add(
                AgentTask(
                    workflow_request_id=workflow_request.id,
                    agent_name=exc.agent_name,
                    input_summary=raw_text[:500],
                    output_summary=None,
                    succeeded=False,
                )
            )
            await session.commit()
            return

        workflow_request.status = WorkflowStatus.COMPLETED
        workflow_request.structured_output = extraction.model_dump(mode="json")
        session.add(
            AgentTask(
                workflow_request_id=workflow_request.id,
                agent_name="triage_agent",
                input_summary=raw_text[:500],
                output_summary=extraction.summary,
                latency_ms=latency_ms,
                succeeded=True,
            )
        )
        await session.commit()

    await _notify_webhook(workflow_request_id, extraction.model_dump(mode="json"))


async def _notify_webhook(workflow_request_id: uuid.UUID, structured_output: dict) -> None:
    if not settings.outbound_webhook_url:
        return

    payload = {
        "workflow_request_id": str(workflow_request_id),
        "status": WorkflowStatus.COMPLETED.value,
        "structured_output": structured_output,
    }

    async with httpx.AsyncClient(timeout=settings.outbound_webhook_timeout_seconds) as client:
        try:
            await client.post(settings.outbound_webhook_url, json=payload)
        except httpx.HTTPError:
            logger.warning(
                "outbound webhook delivery failed for workflow_request_id=%s",
                workflow_request_id,
            )
