# Meta sessions

A meta session is a separate session that inspects previous solver sessions, pulls out patterns, and distills them into doc updates.

`scripts/inspect-session.py` produces the inspection. Pass a session id to inspect one; pass no arg for the multi-session window — from the oldest in-window meta session (inclusive) forward. The window may include later meta sessions; the oldest is the boundary and carries past info forward from before it.

A single mistake or friction is one datapoint — too thin to reliably abstract from. Patterns lift into principles when seen across a spread of sessions; isolated incidents stay logged but unlifted until the data supports the abstraction.
