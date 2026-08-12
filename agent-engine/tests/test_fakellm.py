import json

import pytest

from app.eval.fakellm import CassetteStore, FakeLLM, request_key


@pytest.mark.asyncio
async def test_replay_is_deterministic(tmp_path):
    path = tmp_path / "c.json"
    cassette = CassetteStore(path)
    key = request_key("sys", "user")
    cassette.put(key, {"sql": "SELECT 1"})
    cassette.save()

    fake = FakeLLM(CassetteStore(path), mode="replay")
    r1 = await fake.complete_json("sys", "user")
    r2 = await fake.complete_json("sys", "user")
    assert r1 == r2 == {"sql": "SELECT 1"}


@pytest.mark.asyncio
async def test_replay_miss_raises(tmp_path):
    fake = FakeLLM(CassetteStore(tmp_path / "c.json"), mode="replay")
    with pytest.raises(RuntimeError, match="cassette miss"):
        await fake.complete_json("sys", "user")


@pytest.mark.asyncio
async def test_record_mode_saves_cassette(tmp_path):
    path = tmp_path / "c.json"

    async def real_call(system, user):
        return {"sql": "SELECT 2"}

    fake = FakeLLM(CassetteStore(path), mode="record", real_call=real_call)
    resp = await fake.complete_json("sys", "user")
    assert resp == {"sql": "SELECT 2"}

    data = json.loads(path.read_text(encoding="utf-8"))
    assert request_key("sys", "user") in data


@pytest.mark.asyncio
async def test_hand_edited_cassette_injects_error(tmp_path):
    # hand-edited cassette: return empty SQL (simulates a bad LLM response)
    path = tmp_path / "c.json"
    key = request_key("sys", "user")
    store = CassetteStore(path)
    store.put(key, {"sql": ""})
    store.save()

    fake = FakeLLM(CassetteStore(path), mode="replay")
    resp = await fake.complete_json("sys", "user")
    assert resp["sql"] == ""
