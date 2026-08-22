from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.eval.adversarial import (
    AdversarialObservation,
    AdversarialRunJournal,
    load_manifest,
    run_offline,
    stable_hash,
)


def _obs(unit: str, case_id: str = "adv_s01") -> AdversarialObservation:
    return AdversarialObservation(unit, case_id, "semantic", "question",
                                  "PROFILE_INELIGIBLE", code="OFFLINE_INELIGIBLE")


def test_started_boundary_persists_unique_registry_and_locked_denominators(tmp_path):
    journal = AdversarialRunJournal.start(tmp_path / "run", load_manifest(), "offline")
    data = journal.read()
    assert data["profile_execution_status"] == "STARTED"
    assert len(data["registry"]) == 22
    assert data["locked_case_denominator"] == 11
    assert data["locked_variant_denominator"] == 3


def test_terminal_write_is_create_only_idempotent_cas(tmp_path):
    journal = AdversarialRunJournal.start(tmp_path / "run", load_manifest(), "offline")
    obs = _obs("adv_s01")
    first = journal.write_terminal(obs)
    second = journal.write_terminal(obs)
    assert first == second
    assert len(list(journal.records_dir.glob("*.json"))) == 1
    changed = _obs("adv_s01")
    changed.reason = "different"
    with pytest.raises(RuntimeError, match="CAS conflict"):
        journal.write_terminal(changed)


def test_finalizer_materializes_running_and_pending_once_and_is_idempotent(tmp_path):
    journal = AdversarialRunJournal.start(tmp_path / "run", load_manifest(), "offline")
    journal.mark_running("adv_s01")
    first = journal.finalize(force=True)
    before = {p.name: stable_hash(json.loads(p.read_text())) for p in journal.records_dir.glob("*.json")}
    result_hash = stable_hash(first)
    second = journal.finalize(force=True)
    after = {p.name: stable_hash(json.loads(p.read_text())) for p in journal.records_dir.glob("*.json")}
    assert first["profile_execution_status"] == "ABORTED"
    assert first["product_denominator_status"] == "LOCKED_INCOMPLETE"
    assert first["expected_disposition"]["accuracy"] is None
    assert first["ledger_integrity"]["missing"] == []
    assert before == after
    assert stable_hash(second) == result_hash


def test_finalizer_does_not_steal_live_lease_but_recovers_dead_process(tmp_path):
    journal = AdversarialRunJournal.start(tmp_path / "run", load_manifest(), "offline")
    assert journal.finalize() == {"status": "RUN_IN_PROGRESS"}
    data = journal.read()
    data["pid"] = 999_999_999
    journal.journal_path.write_text(json.dumps(data), encoding="utf-8")
    recovered = journal.finalize()
    assert recovered["profile_execution_status"] == "ABORTED"
    assert recovered["ledger_integrity"]["missing"] == []


def test_sigkill_after_started_is_recovered_from_persistent_journal(tmp_path):
    run_dir = tmp_path / "killed"
    script = (
        "import time; from pathlib import Path; "
        "from app.eval.adversarial import AdversarialRunJournal,load_manifest; "
        f"AdversarialRunJournal.start(Path({str(run_dir)!r}),load_manifest(),'offline'); "
        "time.sleep(60)"
    )
    process = subprocess.Popen([sys.executable, "-c", script], cwd=Path(__file__).parents[1])
    deadline = time.time() + 10
    while not (run_dir / "journal.json").exists() and time.time() < deadline:
        time.sleep(0.02)
    assert (run_dir / "journal.json").exists()
    os.kill(process.pid, signal.SIGKILL)
    process.wait(timeout=5)
    result = AdversarialRunJournal(run_dir).finalize()
    assert result["profile_execution_status"] == "ABORTED"
    assert result["product_denominator_status"] == "LOCKED_INCOMPLETE"
    assert result["ledger_integrity"]["record_count"] == 22


def test_duplicate_terminal_is_not_deduplicated_and_blocks_aggregation(tmp_path):
    journal = AdversarialRunJournal.start(tmp_path / "run", load_manifest(), "offline")
    journal.write_terminal(_obs("adv_s01"))
    duplicate = journal.records_dir / "duplicate-evidence.json"
    duplicate.write_text((journal.records_dir / "adv_s01.json").read_text(), encoding="utf-8")
    result = journal.finalize(force=True)
    assert result["ledger_integrity"]["duplicate"] == ["adv_s01"]
    assert result["product_denominator_status"] == "LOCKED_INVALID"
    assert result["metrics"] is None
    assert result["system_readiness"] == "NOT_ASSESSED"


def test_declared_terminal_without_record_is_missing_and_locked_invalid(tmp_path):
    journal = AdversarialRunJournal.start(tmp_path / "run", load_manifest(), "offline")
    data = journal.read()
    data["registry"]["adv_s01"]["status"] = "TERMINAL"
    journal.journal_path.write_text(json.dumps(data), encoding="utf-8")
    result = journal.finalize(force=True)
    assert result["ledger_integrity"]["missing"] == ["adv_s01"]
    assert result["product_denominator_status"] == "LOCKED_INVALID"


@pytest.mark.parametrize("kind", ["unknown", "orphan"])
def test_unknown_and_orphan_records_fail_ledger_integrity(tmp_path, kind):
    journal = AdversarialRunJournal.start(tmp_path / "run", load_manifest(), "offline")
    unit = "unknown" if kind == "unknown" else "missing_parent::variant"
    payload = _obs(unit, "missing_parent").to_dict()
    (journal.records_dir / f"{kind}.json").write_text(json.dumps(payload), encoding="utf-8")
    result = journal.finalize(force=True)
    assert result["ledger_integrity"][kind]
    assert result["product_denominator_status"] == "LOCKED_INVALID"


def test_offline_profile_completes_with_ineligible_external_cases_single_listed(tmp_path):
    report = run_offline(load_manifest(), tmp_path / "offline")
    assert report["profile_execution_status"] == "COMPLETED"
    assert report["case_coverage"]["total"] == 11  # P01-P05 + C01-C05 + isolated G04
    assert any(o["observation_status"] == "PROFILE_INELIGIBLE" for o in report["observations"])
    assert report["ledger_integrity"]["status"] == "PASS"
