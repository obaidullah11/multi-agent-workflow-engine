import json
import time

from openai import AsyncOpenAI, APITimeoutError, APIError
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.workflow import StructuredExtraction

EXTRACTION_SYSTEM_PROMPT = """You are a triage agent that converts unstructured \
support tickets or leads into structured JSON. Respond with strict JSON matching \
this schema: summary (string), category (string), priority \
(one of: low, medium, high, urgent), sentiment (string), key_entities \
(array of strings), suggested_action (string). Do not include any text outside \
the JSON object."""


class AgentExecutionError(Exception):
    def __init__(self, agent_name: str, reason: str):
        self.agent_name = agent_name
        self.reason = reason
        super().__init__(f"{agent_name} failed: {reason}")


class TriageAgent:
    def __init__(self, client: AsyncOpenAI | None = None):
        settings = get_settings()
        self._client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    async def extract(self, raw_text: str) -> tuple[StructuredExtraction, int]:
        started_at = time.monotonic()

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": raw_text},
                ],
            )
        except APITimeoutError as exc:
            raise AgentExecutionError("triage_agent", "request timed out") from exc
        except APIError as exc:
            raise AgentExecutionError("triage_agent", str(exc)) from exc

        latency_ms = int((time.monotonic() - started_at) * 1000)
        content = response.choices[0].message.content

        try:
            parsed = json.loads(content)
            extraction = StructuredExtraction.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AgentExecutionError(
                "triage_agent", f"invalid model response: {exc}"
            ) from exc

        return extraction, latency_ms
