from pathlib import Path

import pytest

from tallymind.state import TallyMindState, TallyMindStateStore


def test_default_state_has_default_host_port() -> None:
    state = TallyMindState()
    assert state.host == "localhost"
    assert state.port == 9000
    assert state.company is None
    assert state.pending_previews == {}


def test_add_preview_returns_unique_ids() -> None:
    state = TallyMindState()
    id1 = state.add_preview("voucher", "Post sales voucher #1", "<TALLYMESSAGE/>", company="Demo")
    id2 = state.add_preview("voucher", "Post sales voucher #2", "<TALLYMESSAGE/>", company="Demo")
    assert id1 != id2
    assert state.pending_previews[id1]["description"] == "Post sales voucher #1"
    assert state.pending_previews[id1]["kind"] == "voucher"


def test_pop_preview_removes_and_returns_entry() -> None:
    state = TallyMindState()
    preview_id = state.add_preview("ledger", "Create ledger X", "<TALLYMESSAGE/>", company=None)
    entry = state.pop_preview(preview_id)
    assert entry["kind"] == "ledger"
    assert preview_id not in state.pending_previews


def test_pop_preview_missing_id_raises_key_error() -> None:
    state = TallyMindState()
    with pytest.raises(KeyError):
        state.pop_preview("does-not-exist")


def test_store_round_trips_state(tmp_path: Path) -> None:
    store = TallyMindStateStore(tmp_path / "state.json")
    state = store.load()
    state.host = "192.168.1.50"
    state.company = "ACME & Co"
    state.add_preview("voucher", "Post sales voucher", "<TALLYMESSAGE/>", company="ACME & Co")
    store.save(state)

    reloaded = store.load()
    assert reloaded.host == "192.168.1.50"
    assert reloaded.company == "ACME & Co"
    assert len(reloaded.pending_previews) == 1


def test_store_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    store = TallyMindStateStore(tmp_path / "missing.json")
    state = store.load()
    assert state.host == "localhost"
