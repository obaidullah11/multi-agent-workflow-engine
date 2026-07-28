from unittest.mock import AsyncMock

import pytest
from openai import APITimeoutError

from app.services.ai_agent import AgentExecutionError, TriageAgent

pytestmark = pytest.mark.asyncio


async def test_extract_returns_structured_output(mock_openai_response):
    fake_client = AsyncMock()
    fake_client.chat.completions.create.return_value = mock_openai_response(
        {
            "summary": "User cannot log in after password reset.",
            "category": "account_access",
            "priority": "high",
            "sentiment": "frustrated",
            "key_entities": ["login", "password reset"],
            "suggested_action": "Escalate to identity team.",
        }
    )

    agent = TriageAgent(client=fake_client)
    extraction, latency_ms = await agent.extract("I can't log in after resetting my password")

    assert extraction.category == "account_access"
    assert extraction.priority.value == "high"
    assert latency_ms >= 0


async def test_extract_raises_on_timeout():
    fake_client = AsyncMock()
    fake_client.chat.completions.create.side_effect = APITimeoutError(request=AsyncMock())

    agent = TriageAgent(client=fake_client)

    with pytest.raises(AgentExecutionError) as exc_info:
        await agent.extract("some incoming ticket text")

    assert "timed out" in exc_info.value.reason


async def test_extract_raises_on_invalid_json():
    fake_client = AsyncMock()
    response = AsyncMock()
    response.choices = [AsyncMock(message=AsyncMock(content="not valid json"))]
    fake_client.chat.completions.create.return_value = response

    agent = TriageAgent(client=fake_client)

    with pytest.raises(AgentExecutionError) as exc_info:
        await agent.extract("some incoming ticket text")

    assert "invalid model response" in exc_info.value.reason
