"""The reads `state_reads` keeps on disk across processes (`kept_reads`): a
record reused past a change of a file it rests on gives a stale result,
with no failure."""

import os
import sys
from pathlib import Path

import pytest

from tests.conftest import script

script("profile_runs")
state_reads = sys.modules["state_reads"]
kept_reads = sys.modules["kept_reads"]
file_reads = sys.modules["file_reads"]

runs: list[str] = []


@state_reads.state_cache(state_reads.DERIVED, kept=state_reads.Kept.DISK)
def words(path: Path) -> int:
    runs.append("words")
    return len(file_reads.file_text(path).split())


@state_reads.state_cache(state_reads.DERIVED, kept=state_reads.Kept.DISK)
def many(path: Path) -> bool:
    runs.append("many")
    return words(path) > 2


def new_process() -> None:
    """Write the records, and drop what this process holds, as a new
    process starts with none."""
    kept_reads.flush()
    for info in state_reads._reads.values():
        info.held.clear()
    kept_reads.open_store(kept_reads.store().path)
    state_reads.new_state()


def write(path: Path, text: str, tick: int) -> None:
    path.write_text(text)
    os.utime(path, ns=(tick * 10**9, tick * 10**9))


def test_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A kept result stands in a later process while the files it rests on
    stand, and is computed again once one changes, also where it rests on
    them through another kept read whose result changed."""
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "store.sqlite")
    f = tmp_path / "f.txt"
    write(f, "a b c", 1)
    new_process()
    assert many(f) is True

    runs.clear()
    new_process()
    assert many(f) is True
    assert runs == []

    runs.clear()
    write(f, "a b", 2)
    new_process()
    assert many(f) is False
    assert words(f) == 2
    assert runs == ["words", "many"]


def test_flush_retries_a_locked_store_without_losing_reads(tmp_path, monkeypatch):
    """A failed write must leave completed reads for the retirement flush."""
    import sqlite3
    monkeypatch.setattr(kept_reads, "_store", None)
    monkeypatch.setattr(kept_reads, "LOCK_WAIT_SECONDS", 0)
    kept_reads.open_store(tmp_path / "store.sqlite")
    store = kept_reads.store()
    store.connect()
    f = tmp_path / "f.txt"
    f.write_text("a b c")
    state_reads.new_state()
    assert words(f) == 3
    with sqlite3.connect(store.path) as locked:
        locked.execute("BEGIN IMMEDIATE")
        kept_reads.flush()
    new_process()
    runs.clear()
    assert words(f) == 3
    assert runs == []


@pytest.mark.parametrize("change", ["replace", "delete"])
def test_read_first_reached_after_merge_keeps_the_loaded_code_identity(tmp_path, monkeypatch, change):
    entry, dependency = tmp_path / "entry.py", tmp_path / "dependency.py"
    entry.write_text("import dependency\n")
    dependency.write_text("value = 'old'\n")
    monkeypatch.setattr(kept_reads, "module_file", {"entry": entry, "dependency": dependency}.get)
    monkeypatch.setattr(kept_reads, "_codes", {})
    monkeypatch.setattr(kept_reads, "_code_files", None)
    monkeypatch.setattr(kept_reads, "_store", None)
    monkeypatch.setattr(kept_reads.checkout, "ROOT", tmp_path)
    kept_reads.open_store(tmp_path / "reads.sqlite")
    kept_reads.pin_code("entry")
    if change == "delete":
        dependency.unlink()
    else:
        dependency.write_text("value = 'new'\n")
    store = kept_reads.store()
    store.keep("entry:read", "key", "old result")
    kept_reads.flush()
    monkeypatch.setattr(kept_reads, "_code_files", None)
    kept_reads._codes.clear()
    # A replacement running the changed dependency must compute its own result.
    assert store.held("entry:read", "key") is None


def test_required_store_refuses_an_unreadable_store_at_once(tmp_path, monkeypatch):
    monkeypatch.setattr(kept_reads, "_store", None)
    path = tmp_path / "reads.sqlite"
    path.mkdir()
    kept_reads.open_store(path, required=True)
    with pytest.raises(kept_reads.Unavailable, match="cannot be read"):
        kept_reads.store().held("fixture:read", "key")


def test_required_store_refuses_a_failed_batch_and_retains_it(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setattr(kept_reads, "_store", None)
    monkeypatch.setattr(kept_reads, "LOCK_WAIT_SECONDS", 0)
    monkeypatch.setattr(kept_reads, "WRITE_BYTES", 0)
    kept_reads.open_store(tmp_path / "reads.sqlite", required=True)
    store = kept_reads.store()
    store.connect()
    with sqlite3.connect(store.path) as locked:
        locked.execute("BEGIN IMMEDIATE")
        store.keep("fixture:read", "key", "completed")
    kept_reads.flush()
    assert kept_reads.Store(store.path).held("fixture:read", "key") == "completed"


def test_next_state_refuses_a_failed_required_flush(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setattr(kept_reads, "_store", None)
    monkeypatch.setattr(kept_reads, "LOCK_WAIT_SECONDS", 0)
    kept_reads.open_store(tmp_path / "reads.sqlite", required=True)
    store = kept_reads.store()
    store.connect()
    store.keep("fixture:read", "key", "completed")
    with sqlite3.connect(store.path) as locked:
        locked.execute("BEGIN IMMEDIATE")
        state_reads.new_state()
    assert kept_reads.flush()
    other = kept_reads.Store(store.path)
    assert other.held("fixture:read", "key") == "completed"
    other.close()
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "reads.sqlite" / "unopenable", required=True)
    kept_reads.store().keep("fixture:read", "key", "completed")
    with pytest.raises(kept_reads.Unavailable, match="before the next state"):
        state_reads.new_state()


def codes_of(path: Path) -> dict[str, float]:
    import sqlite3
    with sqlite3.connect(path) as db:
        return dict(db.execute("SELECT code, used FROM codes"))


def test_a_write_notes_the_code_of_each_record_it_writes(tmp_path, monkeypatch):
    """A process that ends after a batch write leaves a `codes` row for the
    records, so that they are dropped once the code expires."""
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "store.sqlite")
    store = kept_reads.store()
    store.keep("fixture:read", "key", "written")
    assert store.write(set())
    assert list(codes_of(store.path)) == [kept_reads.code_of("fixture")]


def seeded_store(path: Path, expired: int, blob: bytes = b"x"):
    """A store with `expired` records of a code last used at time 0."""
    file = kept_reads.StoreFile(path, kept_reads.SCHEMA)
    db = file.connect()
    with db:
        db.execute("INSERT INTO codes VALUES ('old', 0)")
        db.executemany("INSERT INTO records VALUES ('old', 'r', ?, ?)",
                       [(str(i), blob) for i in range(expired)])
    return file


def record_count(file) -> int:
    return file.connect().execute("SELECT count(*) FROM records").fetchone()[0]


def test_a_write_drops_a_bounded_batch_of_expired_records_and_later_writes_go_on(tmp_path, monkeypatch):
    monkeypatch.setattr(kept_reads, "DROP_BATCH", 3)
    monkeypatch.setattr(kept_reads, "CLEANUP_SECONDS", 0)
    file = seeded_store(tmp_path / "store.sqlite", 10)
    counts = []
    for _ in range(4):
        assert file.put([], ["new"], 3600)
        counts.append(record_count(file))
    assert counts == [7, 4, 1, 0]
    assert list(codes_of(file.path)) == ["new"]


def test_a_write_gives_back_a_bounded_number_of_free_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(kept_reads, "VACUUM_BATCH", 4)
    monkeypatch.setattr(kept_reads, "CLEANUP_SECONDS", 0)
    file = seeded_store(tmp_path / "store.sqlite", 20, b"x" * 100_000)

    def free_pages() -> int:
        return file.connect().execute("PRAGMA freelist_count").fetchone()[0]

    assert file.put([], ["new"], 3600)
    first = free_pages()
    assert file.put([], ["new"], 3600)
    assert 0 < free_pages() < first
