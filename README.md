# Multi-Agent AI Workflow Engine

A backend service for turning messy, unstructured text — support tickets, inbound leads, contact-form submissions — into structured, actionable data. Drop in a raw message, and it comes back tagged with a category, priority, sentiment, and a suggested next action, ready to route to whatever system needs it.

The point of building it this way was to keep the API responsive no matter how long the AI call takes. Ingestion returns immediately with a task ID; the actual classification work happens in the background and shows up a moment later when you check status (or get pushed to you via webhook).

## How it's put together

- **FastAPI** handles the ingest and status endpoints, async all the way down.
- **Celery, backed by Redis**, does the actual work off the request thread. That's what lets `POST /ingest` come back in milliseconds with a `202` instead of making the caller wait on an LLM round trip.
- **PostgreSQL**, via SQLAlchemy's async engine, is where request and agent-execution history lives — nothing in memory, nothing lost on a restart.
- **OpenAI**, called in JSON mode and validated against a Pydantic schema before it ever touches the database. If the model returns something malformed, that request is marked failed with a reason instead of silently storing garbage.

Each of these pieces only knows about its own job — the API layer doesn't know how classification works, the agent doesn't know about Celery, the worker doesn't know about FastAPI. That's mostly so any one of them can be swapped later without a rewrite (a different LLM provider, a different queue, whatever).

## Getting it running

```bash
cp .env.example .env   # at minimum, drop in your OPENAI_API_KEY
docker compose up --build
```

Once it's up: API at `http://localhost:8000`, Swagger docs at `http://localhost:8000/docs`.

## Using it

### Send something in

```bash
curl -X POST http://localhost:8000/api/v1/workflows/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source": "support_form",
    "payload": {"message": "My last invoice charged me twice, please fix this"}
  }'
```

You'll get back a task ID right away, before the AI has even looked at it:

```json
{
  "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending"
}
```

### Check on it

```bash
curl http://localhost:8000/api/v1/workflows/3fa85f64-5717-4562-b3fc-2c963f66afa6
```

A few seconds later, once the worker's picked it up:

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "completed",
  "structured_output": {
    "summary": "Customer was charged twice on their last invoice.",
    "category": "billing",
    "priority": "high",
    "sentiment": "frustrated",
    "key_entities": ["invoice"],
    "suggested_action": "Escalate to billing team for refund review."
  },
  "failure_reason": null,
  "created_at": "2026-07-29T10:00:00Z",
  "updated_at": "2026-07-29T10:00:04Z"
}
```

If you'd rather not poll, set `OUTBOUND_WEBHOOK_URL` in your `.env` and the same payload gets POSTed there the moment processing finishes.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Everything runs against an in-memory SQLite database with the OpenAI client mocked out, so there's nothing external to spin up just to run the suite.
