"""`ticket_citations.names_of`: which names it gives a `<name>`."""

from engine import checkout
from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()

ticket_citations = script("ticket_citations")


def test_word_and_directories_give_the_name_alone() -> None:
    main = checkout.main_worktree(checkout.ROOT)
    for name in ("engine", "src/engine", "writing.md"):
        assert ticket_citations.names_of(main, name).known == [name]


def test_file_path_gives_its_earlier_paths() -> None:
    known = ticket_citations.names_of(checkout.main_worktree(checkout.ROOT), "scripts/souffle_parity.py").known
    assert "scripts/parity.py" in known
    assert "scripts/souffle_parity.py" in known


def test_commands_keep_broad_references_and_per_name_membership(tmp_path, monkeypatch) -> None:
    from ticketing.vocabulary import Kind, Status

    target = "src/pkg/target.py"
    other = "scripts/other.py"
    former = "src/old/previous.py"
    monkeypatch.setattr(ticket_citations, "main_tree", lambda: tmp_path)
    monkeypatch.setattr(checkout, "git_out", lambda main, *args: former if args[-1] == target else "")
    cases = {
        10: (Status.NEW, Kind.BUG, f"{target} and {other}: both"),
        2: (Status.CLOSED, Kind.PERFORMANCE, f"{former}: former path"),
        3: (Status.CLOSED, Kind.BUG, f"prefix{target}suffix: path substring"),
        4: (Status.NEW, Kind.BUG, "else/target.py: basename after slash"),
        5: (Status.CLOSED, Kind.BUG, "prefix.pkg.target: module after dot"),
        6: (Status.CLOSED, Kind.BUG, "target.py-extra pkg.target-extra: near match"),
        7: (Status.CLOSED, Kind.BUG, "widget: bare word"),
        8: (Status.CLOSED, Kind.BUG, "unrelated: no reference"),
        9: (Status.CLOSED, Kind.BUG, "else/pkg.target: module after slash"),
    }
    last = {}
    for number, (status, kind, title) in cases.items():
        directory = tmp_path / "tickets" / status
        directory.mkdir(parents=True, exist_ok=True)
        last[number] = f"2026-10-20T00:00:00Z {status} [code-editor]: case {number}"
        (directory / f"1-{number}_ticket_example_code-editor.md").write_text(
            f"---\nkind: {kind}\n---\n# {title}\n\n## Log\n"
            f"2026-10-19T00:00:00Z new [code-editor]: filed\n{last[number]}\n")

    expected = []
    for name, known, numbers in (
        (other, [other], [10]),
        (target, [former, target], [2, 3, 4, 5, 9, 10]),
        ("widget", ["widget"], [7]),
        ("absent", ["absent"], []),
    ):
        expected.append(f"{name}: names: {', '.join(known)}")
        for number in numbers:
            status, kind, title = cases[number]
            expected.append(f"    1-{number} {status} {kind} {title}\n        {last[number]}")
        if not numbers:
            expected.append("    the list is empty")
    assert ticket_citations.citing_command([other, target, "widget", "absent"]) == "\n".join(expected)

    expected = [f"names: {other}, {former}, {target}, widget"]
    expected += [f"1-{n} {cases[n][2]}\n    {last[n]}" for n in (2, 3, 5, 7, 9)]
    assert ticket_citations.closed_on_command([other, target, "widget"]) == "\n".join(expected)
    assert ticket_citations.closed_on_command(["absent"]) == "names: absent\nthe list is empty"
