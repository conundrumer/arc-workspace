"""Every message the console sends renders with the values its builder passes.

A message's interface is inferred from `prompts/console.md`, so a value the
builder passes that the document stopped reading, and a value the document
started reading that the builder does not pass, are both errors. Either one
raises where that message is sent, and some stages are reached rarely, so the
break would sit until then.
"""

TID = "007bbfb7"
ITEM = {"id": TID, "reports": {"create": "the create report body"}}
REPORTS = [("create", "the create report body")]


def briefs(s):
    """One call per message the console sends, named for the message."""
    return {
        "create": lambda: s.create_message(TID),
        "advance": lambda: s.advance_message(ITEM, "create", True),
        "advance-last": lambda: s.advance_message(ITEM, "create", False),
        "finalize-bare": lambda: s.finalize_message(TID, []),
        "finalize": lambda: s.finalize_message(TID, REPORTS),
        "handoff": s.handoff_brief,
        "refused-handoff": s.refused_handoff_brief,
        "callout": s.callout_brief,
        "refused-callout": s.refused_callout_brief,
        "nudge": s.nudge_brief,
        "bail": s.bail_brief,
        "handoff-tail": s.handoff_tail,
        "review-tail": s.review_tail,
        "scratch-note": s.scratch_note,
        "survey": lambda: s.survey_brief(
            "docs/wf-solver/proposals/x.md", "programs/", ".scratch/x"),
    }


def test_every_message_the_console_sends_renders(srv):
    for name, call in briefs(srv).items():
        assert call().strip(), name
