# DataAgent Agent Engine

Python Agent orchestration service for the ChatBI / DataAgent platform.

This service owns the LangGraph state-graph orchestration (explicit nodes, conditional
edges, durable human-in-the-loop). The only supported graph mode is `chatbi`.

## Orchestration

- Built with `langgraph` `StateGraph`: 8 chatbi nodes + an `APPROVAL` node.
- Retry loops are expressed as conditional edges back to `SQL_GENERATE` (max 3).
- High-risk SQL pauses at `APPROVAL` via `interrupt()`; approvals resume the same SQL
  with `allow_high_risk=true` (no regeneration → approval-object drift prevented).
- Checkpoints persist in SQLite (`langgraph-checkpoint-sqlite`, aiosqlite), so a
  waiting approval survives process restart and can be resumed by `thread_id == run_id`.

## Local Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

## Endpoints

```text
GET  /health
POST /analyze
POST /runs/{run_id}/approval
```

## Request

```json
{
  "runId": "run_demo",
  "userId": "demo",
  "question": "analyze category play trends",
  "bypassCache": true,
  "graphMode": "chatbi"
}
```

`graphMode` only accepts `chatbi`. The graph runs:

```text
ROUTER -> SCHEMA -> SQL_GENERATE -> SQL_HARD_GUARD -> SQL_EXECUTE
  -> SQL_VALIDATE -> SQL_SOFT_DQ -> ANSWER
```

High-risk SQL branches into `APPROVAL` (interrupt) and waits for
`POST /runs/{run_id}/approval`.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m app.eval.runner --mode mock
```
