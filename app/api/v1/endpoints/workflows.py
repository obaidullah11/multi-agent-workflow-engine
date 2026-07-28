import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WorkflowRequest, WorkflowStatus
from app.db.session import get_db_session
from app.schemas.workflow import (
    WorkflowIngestRequest,
    WorkflowIngestResponse,
    WorkflowStatusResponse,
)
from app.worker.tasks import process_workflow_request

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post(
    "/ingest",
    response_model=WorkflowIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_workflow(
    body: WorkflowIngestRequest,
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowIngestResponse:
    workflow_request = WorkflowRequest(
        source=body.source,
        raw_payload=body.payload,
        status=WorkflowStatus.PENDING,
    )
    session.add(workflow_request)
    await session.commit()
    await session.refresh(workflow_request)

    process_workflow_request.delay(str(workflow_request.id))

    return WorkflowIngestResponse(
        task_id=workflow_request.id,
        status=workflow_request.status.value,
    )


@router.get("/{task_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowStatusResponse:
    workflow_request = await session.get(WorkflowRequest, task_id)

    if workflow_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No workflow request found with id {task_id}",
        )

    return WorkflowStatusResponse.model_validate(workflow_request)
