import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class WorkflowIngestRequest(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    payload: dict = Field(min_length=1)


class WorkflowIngestResponse(BaseModel):
    task_id: uuid.UUID
    status: str


class StructuredExtraction(BaseModel):
    summary: str
    category: str
    priority: Priority
    sentiment: str
    key_entities: list[str] = Field(default_factory=list)
    suggested_action: str


class WorkflowStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    structured_output: StructuredExtraction | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime
