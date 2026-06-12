# DataAgent LangGraph Engine

Python Agent orchestration service for the DataAgent platform.

This service owns the LangGraph-style state machine for the DataAgent platform. The default
`/analyze` flow is the ChatBI/Text2SQL main chain; the older attribution-oriented graph is still
available as `graphMode=full` for compatibility while the main chain is rebuilt.

## Local Run

```bash
uvicorn app.main:app --reload --port 8090
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

`graphMode=full` keeps the legacy side branches:

```text
ROUTER -> SCHEMA -> SQL_GENERATE -> SQL_HARD_GUARD -> SQL_EXECUTE
  -> SQL_VALIDATE -> SQL_SOFT_DQ
  -> RAG -> CROSS_VALIDATE -> INSIGHT -> RECOMMENDATION -> MERGE -> DBQA
```
