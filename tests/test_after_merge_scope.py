"""The steps a change places after its merge are the items of its Scope
that open `After the merge`, and a change whose Scope holds none gets no
after-merge agent."""

import pytest

from tests.conftest import script

INTENT = "---\nkind: change\neditors: code-editor\n---\n# t\n\n## Intent\n- x.\n\n## Motivation\n- y.\n\n"
GROUNDS = "\n## Grounds\n- After the merge: not in the Scope.\n\n## Log\n"


@pytest.mark.parametrize("scope, items", [
    ("- `a.py`.\n- After the merge: run the corpus.\n    - File each difference.\n- `b.py`.\n",
     "- After the merge: run the corpus.\n    - File each difference."),
    ("- After the merge: run x.\n- `a.py`.\n- After the merge, in the main tree: run y.\n",
     "- After the merge: run x.\n- After the merge, in the main tree: run y."),
    ("- `a.py`.\n    - After the merge: a sub-item.\n", None),
])
def test_after_merge_items(scope: str, items: str | None) -> None:
    from handbook.paths import scripts_importable
    scripts_importable()
    text = INTENT + "## Scope\n" + scope + GROUNDS
    assert script("ticket_reads").after_merge(text) == items
