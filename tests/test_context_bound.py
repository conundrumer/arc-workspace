"""The read of the override of the context bound of an operator."""

from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
hook = script("context_bound_hook")


def override(main: Path, text: str) -> Path:
    path = main / hook.OVERRIDE
    path.parent.mkdir(parents=True)
    path.write_text(text)
    return main


@pytest.mark.parametrize("text", ["0", "-5", "5k", "", "1 2"])
def test_override_refuses_what_is_no_positive_whole_number(tmp_path: Path, text: str) -> None:
    assert hook.context_bound(override(tmp_path, text)) == hook.CONTEXT_BOUND


def test_override_holds_where_it_stands(tmp_path: Path) -> None:
    assert hook.context_bound(override(tmp_path, "500000\n")) == 500_000
