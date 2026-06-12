# DataAgent Agent Engine

Python Agent orchestration service for the ChatBI / DataAgent platform.

This service owns the LangGraph-style state machine. The default `/analyze` flow is the
ChatBI/Text2SQL main chain. The older attribution-oriented graph remains available as
`graphMode=full` only for compatibility and is not the current delivery target.

## Local Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

## Endpoints

```text
GET  /health
POST /analyze
```

## Graph Modes

```json
{
  "runId": "run_demo",
  "userId": "demo",
  "question": "analyze category play trends",
  "bypassCache": true,
  "graphMode": "chatbi"
}
```

`graphMode=chatbi` is the default and runs:

```text
ROUTER -> SCHEMA -> SQL_GENERATE -> SQL_HARD_GUARD -> SQL_EXECUTE
  -> SQL_VALIDATE -> SQL_SOFT_DQ -> ANSWER
```

`graphMode=full` keeps legacy side branches for reference:

```text
ROUTER -> SCHEMA -> SQL_GENERATE -> SQL_HARD_GUARD -> SQL_EXECUTE
  -> SQL_VALIDATE -> SQL_SOFT_DQ
  -> RAG -> CROSS_VALIDATE -> INSIGHT -> RECOMMENDATION -> MERGE -> DBQA
```

Use `graphMode=chatbi` for development, tests, and real smoke checks unless a task explicitly
targets legacy attribution behavior.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m app.eval.runner --mode mock
```
