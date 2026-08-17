"""TokenMeter：模块级单例，记录 LLM 调用 token 消耗（OpenAI 兼容 usage）。

用途：eval 指标——直通（跳过解析 LLM）的 token 归零证据 + 每用例 token 归因。
runner 每 case 前后 snapshot 差值 → 归因到该 run；命中 run 差值 ≈ 0（仅解析阶段消除）。
mock/replay 无真实调用，不记录；仅 real 模式有数据。
"""


class TokenMeter:
    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.calls = 0

    def record(self, usage: dict | None) -> None:
        """记录一次 LLM 响应的 usage（prompt/completion/total）；缺失则忽略。"""
        usage = usage or {}
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.total_tokens += int(usage.get("total_tokens") or 0)
        self.calls += 1

    def snapshot(self) -> dict:
        """返回当前累计值（用于 runner 前后快照归因）。"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
        }

    def reset(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.calls = 0


meter = TokenMeter()
