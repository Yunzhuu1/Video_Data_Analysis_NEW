import json
from pathlib import Path

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal local environments.
    httpx = None

from app.settings import settings

# 共享指标字典（与 Java DataInitializer 种子同源，见 src/main/resources/metric_catalog.json）
_METRIC_CATALOG_PATH = Path(__file__).resolve().parents[3] / "src" / "main" / "resources" / "metric_catalog.json"


def _load_metric_catalog() -> list[dict]:
    try:
        return json.loads(_METRIC_CATALOG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


class PlatformClient:
    def __init__(self) -> None:
        self.base_url = settings.platform_base_url.rstrip("/")
        self.headers = {"X-Internal-Token": settings.internal_api_token}

    @staticmethod
    def _require_httpx():
        if httpx is None:
            raise RuntimeError("httpx is required when platform_calls_enabled=true")
        return httpx

    async def health(self) -> dict:
        if not settings.platform_calls_enabled:
            return {"status": "DISABLED"}
        http = self._require_httpx()
        async with http.AsyncClient(timeout=5) as client:
            response = await client.get(f"{self.base_url}/actuator/health", headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def relevant_schema(self, question: str) -> str:
        if not settings.platform_calls_enabled:
            return "schema_context_disabled_for_test"
        http = self._require_httpx()
        async with http.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/internal/schema/relevant",
                headers=self.headers,
                json={"question": question},
            )
            response.raise_for_status()
            return str(response.json()["schemaContext"])

    async def execute_sql(
        self,
        run_id: str,
        user_id: str,
        question: str,
        sql: str,
        purpose: str,
        allow_high_risk: bool = False,
    ) -> dict:
        if not settings.platform_calls_enabled:
            return {
                "success": True,
                "sql": sql,
                "columns": ["date", "category", "total_plays"],
                "rows": [{"date": "2026-01-01", "category": "demo", "total_plays": 100}],
                "rowCount": 1,
                "truncated": False,
                "warnings": [],
                "errorCode": None,
                "error": None,
                "riskLevel": "LOW",
                "accessedTables": ["mock_table"],
                "durationMs": 0,
            }
        http = self._require_httpx()
        async with http.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/internal/sql/execute",
                headers=self.headers,
                json={
                    "runId": run_id,
                    "userId": user_id,
                    "question": question,
                    "sql": sql,
                    "purpose": purpose,
                    "allowHighRisk": allow_high_risk,
                },
            )
            response.raise_for_status()
            return dict(response.json())

    async def validate_sql(
        self,
        run_id: str,
        user_id: str,
        question: str,
        sql: str,
        purpose: str,
        allow_high_risk: bool = False,
        intent: str | None = None,
        intent_time_range_type: str | None = None,
    ) -> dict:
        if not settings.platform_calls_enabled:
            return {
                "verdict": "PASS",
                "code": None,
                "reason": None,
                "suggestion": None,
                "riskLevel": "LOW",
                "accessedTables": ["mock_table"],
            }
        http = self._require_httpx()
        async with http.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/internal/sql/validate",
                headers=self.headers,
                json={
                    "runId": run_id,
                    "userId": user_id,
                    "question": question,
                    "sql": sql,
                    "purpose": purpose,
                    "intent": intent,
                    "intentTimeRangeType": intent_time_range_type,
                    "allowHighRisk": allow_high_risk,
                },
            )
            response.raise_for_status()
            return dict(response.json())

    async def check_sql_result_dq(
        self,
        run_id: str,
        user_id: str,
        question: str,
        query_result: dict,
    ) -> dict:
        if not settings.platform_calls_enabled:
            return {
                "pass": True,
                "riskLevel": "LOW",
                "reason": None,
                "suggestion": None,
                "warnings": [],
            }
        http = self._require_httpx()
        async with http.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/internal/dq/sql-result/check",
                headers=self.headers,
                json={
                    "runId": run_id,
                    "userId": user_id,
                    "question": question,
                    "queryResult": query_result,
                },
            )
            response.raise_for_status()
            return dict(response.json())

    async def metric_catalog(self) -> list[dict]:
        """List active metric definitions (the metric dictionary)."""
        if not settings.platform_calls_enabled:
            return _load_metric_catalog()
        http = self._require_httpx()
        async with http.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.base_url}/internal/metrics", headers=self.headers)
            response.raise_for_status()
            return list(response.json())

    async def metric_definition(self, code: str) -> dict:
        """Fetch a single metric definition by code."""
        if not settings.platform_calls_enabled:
            for m in _load_metric_catalog():
                if m.get("metricCode") == code:
                    return m
            return {
                "metricCode": code,
                "metricName": code,
                "businessDefinition": "unknown metric",
                "formula": "COUNT(*)",
                "sourceTable": "metric_daily",
                "timeField": "date",
                "dimensions": ["date", "category"],
            }
        http = self._require_httpx()
        async with http.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/internal/metrics/{code}", headers=self.headers
            )
            response.raise_for_status()
            return dict(response.json())

    async def lineage_snapshot(self) -> dict:
        """Fetch the immutable lineage+metric+schema snapshot for one run."""
        if not settings.platform_calls_enabled:
            from app.lineage.catalog import load_mock_snapshot

            return load_mock_snapshot()
        http = self._require_httpx()
        async with http.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/internal/lineage/snapshot", headers=self.headers,
            )
            response.raise_for_status()
            return dict(response.json())

    async def start_node(self, run_id: str, node_name: str, input_payload: dict) -> int | None:
        if not settings.trace_callback_enabled:
            return None
        http = self._require_httpx()
        async with http.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/internal/runs/{run_id}/nodes",
                headers=self.headers,
                json={"nodeName": node_name, "inputPayload": input_payload},
            )
            response.raise_for_status()
            return int(response.json()["nodeId"])

    async def finish_node(self, run_id: str, node_id: int | None, output_payload: dict) -> None:
        if not settings.trace_callback_enabled or node_id is None:
            return
        http = self._require_httpx()
        async with http.AsyncClient(timeout=10) as client:
            response = await client.patch(
                f"{self.base_url}/internal/runs/{run_id}/nodes/{node_id}",
                headers=self.headers,
                json={"status": "SUCCESS", "outputPayload": output_payload},
            )
            response.raise_for_status()

    async def fail_node(self, run_id: str, node_id: int | None, error_message: str) -> None:
        if not settings.trace_callback_enabled or node_id is None:
            return
        http = self._require_httpx()
        async with http.AsyncClient(timeout=10) as client:
            response = await client.patch(
                f"{self.base_url}/internal/runs/{run_id}/nodes/{node_id}",
                headers=self.headers,
                json={"status": "FAILED", "errorMessage": error_message},
            )
            response.raise_for_status()
