"""A rendered card carries every candidate's grid, marks a partial one, and
numbers its options."""

from dl import solve
from dl.facts import Candidate
from study import cards


def test_render_shows_each_candidate_and_numbers_the_options(tmp_path, monkeypatch):
    witness = tmp_path / "witness.txt"
    witness.write_text("1 2\n3 4\n")
    code = tmp_path / "slice.dl"
    code.write_text(".decl gap(g: number)\ngap(1).\n")

    def fake_run_dl(task_id, grid, stem=None):
        return [
            Candidate("$Total()", [[1, 2], [3, 4]], [], []),
            Candidate("$Partial()", [[1, -1], [3, 4]], [], [(0, 1)]),
        ]

    monkeypatch.setattr(solve, "run_dl", fake_run_dl)

    card = cards.Card(
        name="t",
        kind="theta",
        task_id="00000000",
        question="one or two?",
        codes=[cards.CodeSlice("slice", str(code), (1, 2), [2])],
        witnesses=[str(witness)],
        options=["first", "second"],
    )
    out = cards.render(card)

    assert "$Total()" in out
    assert "$Partial()" in out
    assert 'class="miss"' in out
    assert "ill-formed: 1 missing" in out
    assert "<ol><li>first</li><li>second</li></ol>" in out


COMPARE_MD = """
### Other table
| task_id | path | case | stratum |
|:--|:--|:--|:--|
| 11111111 | a.dl | Alpha | other |

### Calibration candidates
| task_id   | path      | case     | stratum     |
|:----------|:----------|:---------|:------------|
| 9356391f  | first.dl  | Survive  | peer-priors |
| 9356391f  | second.dl | Survive  | peer-priors |
| 9385bd28  | third.dl  | Triomino | peer-priors |

calibration needed: yes (3)
"""


def test_parse_candidates_reads_one_table_and_keeps_the_first_path():
    rows = cards.parse_candidates(COMPARE_MD)

    assert rows == [
        ("9356391f", "first.dl", "Survive", "peer-priors"),
        ("9385bd28", "third.dl", "Triomino", "peer-priors"),
    ]
