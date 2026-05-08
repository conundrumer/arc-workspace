# Meta sessions

A meta session is a separate session that inspects previous solver sessions, pulls out patterns, and distills them into doc updates.

`scripts/inspect-session.py` produces the inspection. Pass a session id to inspect one; pass no arg for the multi-session window — from the boundary (oldest in-window meta session, inclusive) forward. The window may include later meta sessions; the boundary carries past info forward from before it.

Read the inspection output in full; piping to `head` truncates the data the meta session is supposed to triage from.

A single mistake or friction is one datapoint — too thin to reliably abstract from. Patterns lift into principles when seen across a spread of sessions; isolated incidents stay logged but unlifted until the data supports the abstraction.

## `drain`

User trigger to surface what should be addressed — tensions to resolve and defaults to codify. Look across all levels (user signals, claude behavior, conversation, artifacts, session rhythm, project, apparatus). Surface broadly; let the user decide. Default is to walk items as they come; `drain` fires when the user wants exhaustive coverage.

A meta session ends by inlining a standing log — items raised in the session that aren't closed (whether engaged or still pending). Each entry has:

- **id**
- **description**
- **origin** — `marker` (user used `defer:`, `queue:`, or related markers), `flag` (user critiqued or articulated without keyword), or `observed` (claude observed and tracked)
- **defer count** — extent of existence; sessions the item has been carried
- **instance count** — occurrences, if applicable
- **last seen** — this session, or N sessions back
- **status** — free-form; reflects how the session engaged with the item

Closed items are omitted. The log lives in the session's final messages; the next meta session picks it up via inspection. Items may persist across many sessions; they aren't dropped.
