"""The transcript cut a refused ask gets."""

import json

from .conftest import transcript

REFUSAL = ("API Error: Fable 5's safeguards flagged this message (https://x). "
           "This sometimes happens with safe, normal conversations.\n\n"
           "Details: `[reasoning_extraction]`\n\nRequest ID: req_2")


def user_row(text, **kw):
    return {"type": "user", "message": {"role": "user", "content": text}, **kw}


def test_strip_ask_cuts_the_transcript_back_to_before_the_ask(srv, monkeypatch,
                                                              tmp_path):
    kept = [user_row("first turn"), {"type": "assistant", "message": {"content": []}}]
    blocks = user_row([{"type": "text", "text": "the ask"}])
    path = transcript(srv, monkeypatch, tmp_path, "sess-a", kept + [
        user_row("the ask", isSidechain=True),     # a subagent's own row
        blocks, {"type": "assistant", "isApiErrorMessage": True,
                 "message": {"content": [{"type": "text", "text": REFUSAL}]}}])
    assert srv.strip_ask(path, "the ask") == 2
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows == kept + [user_row("the ask", isSidechain=True)]
    assert srv.strip_ask(path, "the ask") == 0      # the sidechain row is not the ask


