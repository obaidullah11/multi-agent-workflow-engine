import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import WorkflowRequest, WorkflowStatus
from app.db.session import get_db_session
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_celery_dispatch():
    with patch("app.api.v1.endpoints.workflows.process_workflow_request.delay") as mock_delay:
        yield mock_delay


@pytest_asyncio.fixture
async def completed_workflow_request(db_session):
    workflow_request = WorkflowRequest(
        id=uuid.uuid4(),
        source="support_form",
        status=WorkflowStatus.COMPLETED,
        raw_payload={"message": "My invoice is wrong"},
        structured_output={
            "summary": "Customer disputes an invoice amount.",
            "category": "billing",
            "priority": "high",
            "sentiment": "frustrated",
            "key_entities": ["invoice"],
            "suggested_action": "Escalate to billing team.",
        },
    )
    db_session.add(workflow_request)
    await db_session.commit()
    await db_session.refresh(workflow_request)
    return workflow_request


@pytest.fixture
def mock_openai_response():
    def _build(content: dict):
        response = AsyncMock()
        response.choices = [AsyncMock(message=AsyncMock(content=json.dumps(content)))]
        return response

    return _build
