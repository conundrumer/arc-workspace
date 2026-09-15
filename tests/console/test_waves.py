"""The state a restart loads."""

import json


def test_load_ends_turns_a_restart_cut_short(srv):
    state = {"seq": 1, "wave": 1, "items": [
        {"id": "a", "state": srv.RUNNING, "session": "s", "feed": [], "ver": 0},
        {"id": "b", "state": srv.COMMENTED, "session": None, "feed": [], "ver": 0},
    ]}
    srv.STATE_FILE.write_text(json.dumps(state))
    srv.load()
    a, b = srv.STATE["items"]
    assert a["state"] == srv.NEEDS_REVIEW  # had a session to resume
    assert b["state"] == srv.QUEUED        # never reported one
    assert b["feed"][-1]["text"] == "interrupted by console restart"


