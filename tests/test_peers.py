"""`peers`: the scratch programs a session did not ship, the ground its
report gives for each, and what they do on the task's pairs."""

from pathlib import Path

import pytest

from dl.solve import PairResult, VariantResult
from study import peers
from study.peers import Row

TASK = "abcd1234"

SOLVER = """\
// the shipped solver
.decl out(p: Position, col: Color)
out(p, c) :- seed(p, c).
"""

FINALIZE = """\
# abcd1234 — finalize

## Peer models considered and dropped

1. `stacking_peer` reproduces no train pair, so it is not a model of this task.
2. `nearest_line` parses the task as the solver does and claims the same
   prior, so under Peer priors it shares the solver's case.
3. The crossing-parity reading gets no case: no pair exercises it.
4. Two peers were considered and dropped.

## Notes

`point_group` names the stored group. Nothing here says a model was dropped.
"""

RETRO = """\
# abcd1234 — retro

The enumerating program subsumes `$Stored`, so the peer is dropped.
"""


def _report(tmp_path: Path, task: str = TASK) -> Path:
    root = tmp_path / "reports" / task
    root.mkdir(parents=True)
    (root / "finalize.md").write_text(FINALIZE)
    (root / "retro.md").write_text(RETRO)
    return tmp_path / "reports"


# --- the grounds a report states ---


def test_stratum_comes_from_the_name_s_own_block(tmp_path):
    mentions, rows = peers.mine_reports(TASK, _report(tmp_path))
    strata = dict(mentions)
    assert strata["stacking_peer"] == "fit"
    assert strata["nearest_line"] == "peer-priors"
    assert strata["$Stored"] == "subsumed"


def test_a_block_that_states_no_ground_is_unnamed(tmp_path):
    _, rows = peers.mine_reports(TASK, _report(tmp_path))
    strata = [row.stratum for row in rows]
    assert "unnamed" in strata
    assert all(row.source == "report" and row.path is None for row in rows)


def test_a_block_naming_no_drop_is_skipped(tmp_path):
    mentions, _ = peers.mine_reports(TASK, _report(tmp_path))
    assert "point_group" not in dict(mentions)


def test_a_named_block_yields_no_report_row(tmp_path):
    _, rows = peers.mine_reports(TASK, _report(tmp_path))
    assert len(rows) == 2  # the two list items that name nothing


@pytest.mark.parametrize("text, stratum", [
    ("it does not fit the third pair", "fit"),
    ("a restatement of the shipped rule", "restatement"),
    ("the shipped case subsumes it", "subsumed"),
    ("two candidates that parse alike", "peer-priors"),
    ("the branch is unexercised in every pair", "exercised"),
    ("no pair exercises the branch", "unnamed"),
    ("the peer stores the group", "unnamed"),
])
def test_block_stratum(text, stratum):
    assert peers.block_stratum(text) == stratum


# --- matching one side to the other ---


@pytest.mark.parametrize("peer, report, how", [
    ("peer_lr", "peer-lr", "exact"),
    ("lattice", "peer_lattice", "suffix"),
    ("stacking", "$Stacking", "exact"),
    ("nearest_lines", "nearest_line", "close"),
])
def test_match_names(peer, report, how):
    pairs, left = peers.match_names([peer], [report])
    assert pairs[peer] == (report, how)
    assert left == []


def test_an_unmatched_name_is_left_over():
    pairs, left = peers.match_names(["wallpaper"], ["$Stored"])
    assert pairs == {}
    assert left == ["$Stored"]


def test_peer_name_drops_the_task_id_and_one_separator():
    assert peers.peer_name_of(f"{TASK}-trans.dl", TASK) == "trans"
    assert peers.peer_name_of(f"{TASK}_alt.dl", TASK) == "alt"
    assert peers.peer_name_of("peer_lattice.dl", TASK) == "peer_lattice"
    assert peers.peer_name_of(f"{TASK}.dl", TASK) == TASK


# --- the programs on disk ---


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    solvers = tmp_path / "solvers"
    solvers.mkdir()
    (solvers / f"{TASK}.dl").write_text(SOLVER)
    scratch = tmp_path / "scratch" / TASK
    scratch.mkdir(parents=True)
    return tmp_path / "scratch", solvers


def test_a_file_that_differs_only_in_comments_is_a_copy(tmp_path):
    root, solvers = _tree(tmp_path)
    (root / TASK / "same.dl").write_text(
        "/* another note */\n.decl out(p: Position, col: Color)\n"
        "out(p, c) :- seed(p, c).  // a trailing note\n")
    (root / TASK / "other.dl").write_text(
        SOLVER.replace("seed(p, c)", "seed(p, c), keep(p)"))
    rows = {r.peer_name: r for r in peers.scan_scratch(root, solvers)}
    assert rows["same"].is_copy
    assert not rows["other"].is_copy


def test_a_copy_name_is_a_copy_whatever_it_holds(tmp_path):
    root, solvers = _tree(tmp_path)
    (root / TASK / "orig.dl").write_text(
        SOLVER.replace("seed(p, c)", "seed(p, c), keep(p)"))
    rows = {r.peer_name: r for r in peers.scan_scratch(root, solvers)}
    assert rows["orig"].is_copy


# --- matching by the identifiers a program declares ---


CHOICE_PEER = """\
.type Choice = Stack {} | Fold {}
.decl out(p: Position, col: Color, c: Choice)
.decl stack_seed(p: Position)
out(p, c, $Stack()) :- stack_seed(p), seed(p, c).
"""


def test_own_names_drops_what_the_shipped_solver_declares():
    own = peers.own_names(CHOICE_PEER, SOLVER)
    assert set(own) == {"stack", "fold", "stackseed"}
    assert own["stackseed"] == "stack_seed"


def test_a_peer_is_placed_by_the_identifiers_it_shares(tmp_path):
    root, solvers = _tree(tmp_path)
    (root / TASK / "v2.dl").write_text(CHOICE_PEER)
    reports = tmp_path / "reports" / TASK
    reports.mkdir(parents=True)
    (reports / "finalize.md").write_text(
        "`nothing_here` names no peer, and the case subsumes it.\n\n"
        "`$Stack` and `stack_seed` are a dropped peer, a restatement of the shipped rule.\n")
    rows, unmatched = peers.inventory(root=root, reports=tmp_path / "reports",
                                      solvers=solvers)
    row = next(r for r in rows if r.peer_name == "v2")
    assert row.matched_by == "identifiers"
    assert row.stratum == "restatement"
    assert row.shared_names == "Stack, stack_seed"
    assert row.report_name == "$Stack"
    assert unmatched == [f"{TASK}\treport\tnothing_here"]


def test_a_peer_sharing_no_identifier_stays_unmatched(tmp_path):
    root, solvers = _tree(tmp_path)
    (root / TASK / "v2.dl").write_text(CHOICE_PEER)
    reports = tmp_path / "reports" / TASK
    reports.mkdir(parents=True)
    (reports / "finalize.md").write_text("`other_rel` is subsumed.\n")
    rows, unmatched = peers.inventory(root=root, reports=tmp_path / "reports",
                                      solvers=solvers)
    row = next(r for r in rows if r.peer_name == "v2")
    assert row.matched_by == "" and row.stratum == ""
    assert f"{TASK}\tpeer\tv2" in unmatched


def test_a_file_without_out_is_skipped(tmp_path):
    root, solvers = _tree(tmp_path)
    (root / TASK / "probe.dl").write_text(".decl seed(p: Position)\n")
    assert peers.scan_scratch(root, solvers) == []


# --- what the programs do on the pairs ---


def _pair(kind: str, idx: int, grids: list, ok: bool = True) -> PairResult:
    return PairResult(
        kind=kind, idx=idx, ok=ok,
        variants=[VariantResult(name=name, ok=ok, actual=grid)
                  for name, grid in grids],
    )


def _ill(kind: str, idx: int) -> PairResult:
    return PairResult(
        kind=kind, idx=idx, ok=False,
        variants=[VariantResult(name="", ok=False, actual=[[0]],
                                error="no grid")],
    )


A = [[1]]
B = [[2]]


@pytest.fixture
def runs(monkeypatch):
    """Hand each stem a canned result per pair, and name two pairs."""
    table: dict[str, list[PairResult]] = {}
    monkeypatch.setattr(peers, "_pairs_of",
                        lambda task_id: [("train", 0, None), ("test", 0, None)])
    monkeypatch.setattr(peers, "res_out_stem", lambda stem: False)

    def fake_run_pair(stem, task_id, kind, idx, ex):
        for result in table[stem]:
            if result.kind == kind and result.idx == idx:
                return result
        raise AssertionError(f"no result for {stem} {kind}[{idx}]")

    monkeypatch.setattr(peers, "run_pair", fake_run_pair)
    return table


def _row(tmp_path: Path) -> Row:
    return Row(task_id=TASK, source="scratch", path=tmp_path / "peer.dl",
               peer_name="peer")


def test_a_peer_on_a_shipped_case_diverges_on_no_pair(runs, tmp_path):
    runs[TASK] = [_pair("train", 0, [("$P", A), ("$Q", B)]),
                  _pair("test", 0, [("$P", A), ("$Q", B)])]
    row = _row(tmp_path)
    runs[str(row.path)] = [_pair("train", 0, [("", B)]),
                           _pair("test", 0, [("", B)])]
    peers.run_rows([row])
    assert row.runs
    assert (row.pairs_passed, row.pairs_total) == (2, 2)
    assert row.pairs_diverging == 0
    assert (row.nearest_case, row.pairs_matching_case) == ("Q", 2)
    assert row.pairs_illformed == 0


def test_a_peer_off_every_case_diverges_on_every_pair(runs, tmp_path):
    runs[TASK] = [_pair("train", 0, [("$P", A)]), _pair("test", 0, [("$P", A)])]
    row = _row(tmp_path)
    runs[str(row.path)] = [_pair("train", 0, [("", B)], ok=False),
                           _pair("test", 0, [("", B)], ok=False)]
    peers.run_rows([row])
    assert row.pairs_diverging == 2
    assert row.pairs_passed == 0
    assert row.pairs_matching_case == 0


def test_an_unreadable_grid_counts_as_illformed(runs, tmp_path):
    runs[TASK] = [_pair("train", 0, [("$P", A)]), _pair("test", 0, [("$P", A)])]
    row = _row(tmp_path)
    runs[str(row.path)] = [_ill("train", 0), _pair("test", 0, [("", A)])]
    peers.run_rows([row])
    assert row.pairs_illformed == 1
    assert row.pairs_diverging == 1
    assert row.pairs_matching_case == 1


def test_a_copy_is_not_run(runs, tmp_path):
    row = _row(tmp_path)
    row.is_copy = True
    peers.run_rows([row])
    assert row.runs is None and row.pairs_total is None
