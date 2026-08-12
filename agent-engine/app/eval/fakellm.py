"""FakeLLM 录制回放：把真实 LLM 请求/响应录成 cassette，离线回放。

- record 模式：调用 real_call 并把 {hash(messages): response} 写入 cassette。
- replay 模式：按请求哈希查表返回；未命中报错（提示重新录制）。
- cassette 是纯 JSON，可手工编辑注入错误响应（空 SQL/坏 JSON/retryable 错误）。
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

RealCall = Callable[[str, str], Awaitable[dict[str, Any]]]


class CassetteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict[str, Any] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def put(self, key: str, response: Any) -> None:
        self._data[key] = response

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def request_key(system_prompt: str, user_prompt: str) -> str:
    payload = system_prompt + "\n@@\n" + user_prompt
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


class FakeLLM:
    def __init__(
        self,
        cassette: CassetteStore,
        mode: str = "replay",
        real_call: RealCall | None = None,
    ) -> None:
        self.cassette = cassette
        self.mode = mode
        self.real_call = real_call

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        key = request_key(system_prompt, user_prompt)
        if self.mode == "replay":
            response = self.cassette.get(key)
            if response is None:
                raise RuntimeError(
                    f"cassette miss for request {key[:12]}...; "
                    "re-record with EVAL_LLM_MODE=record"
                )
            return response
        if self.real_call is None:
            raise RuntimeError("record mode requires real_call")
        response = await self.real_call(system_prompt, user_prompt)
        self.cassette.put(key, response)
        self.cassette.save()
        return response
