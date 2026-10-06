"""The Θ card: one card defined in code, whose table is a corpus scan."""

from cli.common import all_stems
from study.card_spec import Card, CodeSlice, Option, Table
from study.corpus_scan import equal_literal_corpus


def theta_card() -> Card:
    """The Θ card for 5d2a5c43: its Params comp states `gap(1)` and
    `divide_gap(1)`, and the user rules on whether that is one parameter."""
    path = "programs/solvers/5d2a5c43.dl"
    corpus = equal_literal_corpus()
    rows = [
        [stem, ", ".join(names), str(value)]
        for stem, value, names in corpus[:10]
    ]
    table = Table(
        title=f"Solvers with equal-literal Params numbers: {len(corpus)} of "
              f"{len(all_stems())}",
        headers=["stem", "relations", "literal"],
        rows=rows,
    )
    return Card(
        name="theta-5d2a5c43",
        kind="theta",
        task_id="5d2a5c43",
        solver=path,
        question=(
            "`gap(1)` and `divide_gap(1)` state the same literal in the same "
            "Params comp: one parameter or two?"
        ),
        codes=[
            CodeSlice("Params comp", path, (32, 73), [43, 55]),
            CodeSlice("reads gap: Params.tile_decompose", path, (44, 48), [47]),
            CodeSlice("reads params.divide_gap: decompose $Count, $Size",
                      path, (89, 99), [93, 97]),
        ],
        options=[
            Option("One parameter: the two facts state one value, and the "
                   "second is derived from the first."),
            Option("Two parameters: a sibling task could assign them "
                   "different values."),
        ],
        tables=[table],
    )
