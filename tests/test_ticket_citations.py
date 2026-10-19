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
