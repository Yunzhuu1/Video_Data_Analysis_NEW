from app.clients.token_meter import TokenMeter


def test_record_and_snapshot():
    m = TokenMeter()
    m.record({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
    m.record({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    snap = m.snapshot()
    assert snap["prompt_tokens"] == 110
    assert snap["completion_tokens"] == 55
    assert snap["total_tokens"] == 165
    assert snap["calls"] == 2


def test_record_tolerates_missing_usage():
    m = TokenMeter()
    m.record({})
    m.record(None)
    assert m.snapshot()["total_tokens"] == 0
    assert m.snapshot()["calls"] == 2


def test_snapshot_diff_for_attribution():
    m = TokenMeter()
    before = m.snapshot()
    m.record({"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50})
    after = m.snapshot()
    assert after["total_tokens"] - before["total_tokens"] == 50


def test_reset():
    m = TokenMeter()
    m.record({"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    m.reset()
    assert m.snapshot()["total_tokens"] == 0
    assert m.snapshot()["calls"] == 0
