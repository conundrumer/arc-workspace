"""The determination plan's rendering."""

from dl.determination_plan import POSITION_DOMAIN_NOTE, render_determination_plan


def plan(results):
    return render_determination_plan((results, [], set()))


def test_the_position_domain_note_marks_a_position_count_over_budget():
    lines = plan([
        ("params.anchor", {"position-domain": "enumerable(64)"}),
        ("params.width", {"domain": "enumerable(9)"}),
    ])
    assert POSITION_DOMAIN_NOTE in lines
    assert lines.index(POSITION_DOMAIN_NOTE) == lines.index("  params.width(9)") + 1


def test_the_position_domain_note_is_absent_without_a_position_count():
    lines = plan([
        ("params.height", {"domain": "enumerable(64)"}),
        ("params.width", {"domain": "enumerable(9)"}),
    ])
    assert any("over the settle budget" in line for line in lines)
    assert POSITION_DOMAIN_NOTE not in lines
