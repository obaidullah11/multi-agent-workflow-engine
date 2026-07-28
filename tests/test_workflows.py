import uuid

import pytest

from app.db.models import WorkflowRequest

pytestmark = pytest.mark.asyncio


async def test_ingest_workflow_returns_202_and_dispatches_task(client, db_session, mock_celery_dispatch):
    response = await client.post(
        "/api/v1/workflows/ingest",
        json={"source": "support_form", "payload": {"message": "The app keeps crashing on login"}},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert uuid.UUID(body["task_id"])

    stored = await db_session.get(WorkflowRequest, uuid.UUID(body["task_id"]))
    assert stored is not None
    assert stored.raw_payload == {"message": "The app keeps crashing on login"}

    mock_celery_dispatch.assert_called_once_with(body["task_id"])


async def test_ingest_workflow_rejects_empty_payload(client):
    response = await client.post(
        "/api/v1/workflows/ingest",
        json={"source": "support_form", "payload": {}},
    )

    assert response.status_code == 422


async def test_ingest_workflow_rejects_missing_source(client):
    response = await client.post(
        "/api/v1/workflows/ingest",
        json={"payload": {"message": "hello"}},
    )

    assert response.status_code == 422


async def test_get_workflow_status_returns_completed_result(client, completed_workflow_request):
    response = await client.get(f"/api/v1/workflows/{completed_workflow_request.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["structured_output"]["category"] == "billing"
    assert body["structured_output"]["priority"] == "high"


async def test_get_workflow_status_returns_404_for_unknown_id(client):
    response = await client.get(f"/api/v1/workflows/{uuid.uuid4()}")

    assert response.status_code == 404
    assert "No workflow request found" in response.json()["detail"]
