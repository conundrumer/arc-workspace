"""The witness file: writers of one file at once each keep their entries, a
file off the shape is not written over, and the reader takes no entry off
the shape. Each would pass silently in use."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from solver import witness
from solver.problems import Expected, InWitnessFile, ProblemKind, ShapeFault
from solver.witness import Entry, Group, Groups, RejectedOutput, Undefined
from tests.solver.fake import grid

G = grid("1 2",
         "3 4")


def entry(id: str) -> Entry:
    return Entry(id, "a against b", G, (),
                 Groups((Group(("A",), G), Group(("B",), Undefined()))))


def test_writers_keep_each_others_entries(tmp_path: Path) -> None:
    at = tmp_path / "0000aaaa.wit.json"
    ids = [f"w{i}" for i in range(16)]
    with ThreadPoolExecutor(8) as pool:
        got = list(pool.map(
            lambda i: witness.put(at, "0000aaaa", [entry(i)]), ids))
    assert got == [()] * len(ids)
    file, problems = witness.read(at.read_text())
    assert problems == ()
    assert file is not None
    assert sorted(e.id for e in file.entries) == sorted(ids)


def test_put_replaces_by_id_and_keeps_the_rest(tmp_path: Path) -> None:
    at = tmp_path / "0000aaaa.wit.json"
    witness.put(at, "0000aaaa", [entry("a"), entry("b")])
    changed = Entry("a", "changed", G, (), RejectedOutput(G))
    witness.put(at, "0000aaaa", [changed])
    file, _ = witness.read(at.read_text())
    assert file is not None
    assert file.entries == (changed, entry("b"))


def test_off_shape_file_is_not_written(tmp_path: Path) -> None:
    at = tmp_path / "0000aaaa.wit.json"
    at.write_text('{"id": "0000aaaa", "witnesses": [{"id": "x"}]}')
    problems = witness.put(at, "0000aaaa", [entry("a")])
    assert problems
    assert at.read_text() == '{"id": "0000aaaa", "witnesses": [{"id": "x"}]}'


def test_reader_leaves_out_entries_off_the_shape() -> None:
    text = """{"id": "0000aaaa", "witnesses": [
      {"id": "ok", "separates": "s", "input": [[1]], "output": [[2]]},
      {"id": "ragged", "separates": "s", "input": [[1], [1, 2]],
       "output": [[2]]},
      {"id": "no-cases", "separates": "s", "input": [[1]],
       "output": [{"grid": [[1]]}]},
      {"id": "extra", "separates": "s", "input": [[1]], "output": [[2]],
       "note": "x"}]}"""
    file, problems = witness.read(text)
    assert file is not None
    assert [e.id for e in file.entries] == ["ok", "extra"]
    assert {p.kind for p in problems} == {ProblemKind.WITNESS_FILE_SHAPE}
    assert {(p.place, p.detail) for p in problems} == {
        (InWitnessFile("ragged"), ShapeFault(("input",), Expected.GRID)),
        (InWitnessFile("no-cases"),
         ShapeFault(("output", 0, "cases"), Expected.PRESENT)),
        (InWitnessFile("extra"), ShapeFault(("note",), Expected.ABSENT)),
    }
