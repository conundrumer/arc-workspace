"""Dashboard ordering, bundle rows, and updates when ticket logs change."""

from pathlib import Path
from dataclasses import replace
import re
from xml.etree import ElementTree as ET

import pytest

from handbook.paths import scripts_importable
from operations.pacing import Usage
from operations.roles import Role
from operations.state import LogLine, Ticket
from ticketing.vocabulary import Domain, Kind, Status
from tests.conftest import script

scripts_importable()
dashboard = script("dashboard_html")
reads = script("dashboard_reads")
shown = script("shown_state")
standings = script("dashboard_standings")


def element(root: ET.Element, path: str) -> ET.Element:
    found = root.find(path)
    assert found is not None, path
    return found


def ticket(n: int, **kwargs) -> Ticket:
    return replace(Ticket(
        number=f"1-{n}", order=(1, n), session=1, status=Status.NEW,
        kind=Kind.BUG, domain=Domain.TICKET, subject="dashboard", filer="coordinator",
        filed=float(n), title=f"dashboard: ticket {n}", depends_on=(), motivation=(),
        editors=None, after_merge=None, mechanical=False, log=(), allowers=(),
        holder=None, path=Path(f"{n}.md")), **kwargs)


def view(tickets, *, agents=(), starts=(), paused=False, own_scope=False, in_scope=None):
    record = shown.Shown(1000, None, shown.ScriptAdmits(True), paused, own_scope,
                         in_scope, (), tuple(agents), {}, None, tuple(starts))
    records = reads.OperatorRecords((reads.SessionRecord(1, record),), None)
    return dashboard.View({t.number: t for t in tickets}, records, Usage(1000, {}),
                          1000, records.expedited(), records.agents(), records.starts(),
                          {s.number: s.held for s in starts if s.held is not None}, {})


def test_page_section_order_and_all_open_work(tmp_path, monkeypatch):
    working = ticket(1)
    held = ticket(2, status=Status.ASSIGNED, filer="code-reviewer")
    ready = ticket(3)
    v = view([working, held, ready], agents=[shown.ShownAgent(Role.CODE_EDITOR, 990, (working.number,))])
    monkeypatch.setattr(dashboard, "read_tickets", lambda _: (v.all_, []))
    monkeypatch.setattr(dashboard, "journal_work", lambda _: {})
    usage = script("usage_limit")
    rendered = dashboard.page(tmp_path, v.now, usage.Reading(usage.Limit.UNKNOWN, None, v.usage),
                              v.records, []).text
    assert re.findall(r'<h2 id="([^"]+)"', rendered) == [
        "health", "active", "queued", "sl", "blocked", "done", "pace", "queue", "find"]
    active = rendered.split('<h2 id="active">')[1].split('<h2')[0]
    queued = rendered.split('<h2 id="queued">')[1].split('<h2')[0]
    assert f'data-n="{working.number}"' in active
    assert all(f'data-n="{t.number}"' in queued for t in (held, ready))
    assert "Your work" not in rendered


@pytest.mark.parametrize("paused", [False, True])
def test_queued_group_order_and_rows_without_ordinals(paused):
    ready = ticket(1)
    waiting = ticket(2, depends_on=(ready.number,))
    held = ticket(3, status=Status.ASSIGNED)
    behind = ticket(4, depends_on=(held.number,))
    request = ticket(5, kind=Kind.REQUEST, goal="A request in this session")
    no_operator = ticket(6, kind=Kind.CHANGE, session=2, motivation=(request.number,))
    on_hold = ticket(7, status=Status.BLOCKED)
    outside = ticket(8)
    deferred = ticket(9, status=Status.DEFERRED)
    tickets = [ready, waiting, held, behind, request, no_operator, on_hold, outside, deferred]
    v = view(tickets, paused=paused, own_scope=True, starts=[shown.Start(held.number, shown.Hold.TAKES)],
             in_scope=frozenset(t.number for t in tickets if t is not outside))
    root = ET.fromstring(dashboard.queued(v, standings.Standings(v)).replace(" open>", ' open="">'))
    pane = element(root, "./div[@class='pane']")
    labels = ["".join((element(el, "summary") if el.tag == "details" else el).itertext()).split(" · ")[0]
              for el in pane if el.get("class") == "gh" or el.tag == "details"]
    assert labels == ["Next on resume" if paused else "Next", "Waiting", "Held by a line",
                      "Behind held work", "No operator running", "On hold by you",
                      "Outside its own work", "Deferred"]
    assert root.find(".//span[@class='wq']") is None
    assert all("ld" not in el.get("class", "").split() for el in root.iter("div"))


def test_next_rows_keep_operator_order():
    tickets = [ticket(1), ticket(2)]
    v = view(tickets, starts=[shown.Start(t.number, None) for t in tickets])
    root = ET.fromstring(dashboard.queued(v, standings.Standings(v)))
    assert [row.get("data-n") for row in root.findall(".//div[@class='wr me tk']")] == [
        t.number for t in tickets]


@pytest.mark.parametrize("status", [Status.ASSIGNED, Status.WAITING, Status.APPROVED])
@pytest.mark.parametrize("hold, expected", [
    (None, standings.Standing.READY),
    (shown.Hold.PAUSE, standings.Standing.READY),
    (shown.Hold.PACE, standings.Standing.READY),
    (shown.Hold.TAKES, standings.Standing.HELD),
    (shown.Hold.OWN_SCOPE, standings.Standing.OWN_SCOPE),
])
def test_only_an_actual_line_holds_idle_work(status, hold, expected):
    t = ticket(1, status=status)
    v = view([t], starts=[] if hold is None else [shown.Start(t.number, hold)], paused=True)
    assert standings.Standings(v).state(t)[0] is expected


@pytest.mark.parametrize("draft", [False, True])
@pytest.mark.parametrize("start_hold", [False, True])
def test_waiting_work_keeps_its_blocker(draft, start_hold):
    blocker = ticket(2, kind=Kind.CHANGE, status=Status.DRAFT if draft else Status.ASSIGNED)
    t = ticket(1, status=Status.WAITING, log=(
        LogLine(50, Status.WAITING, "ticket-analyst", None, "waiting", False,
                None if start_hold else blocker.number, True, None, None, None),))
    v = view([t, blocker], starts=[shown.Start(t.number, shown.OnTicket(blocker.number))] if start_hold else [])
    assert standings.Standings(v).state(t) == (standings.Standing.WAITING, blocker)


@pytest.mark.parametrize("status, hold", [
    (Status.ASSIGNED, None), (Status.ASSIGNED, shown.Hold.TAKES),
    (Status.BLOCKED, None), (Status.DEFERRED, None),
])
@pytest.mark.parametrize("stage", [reads.Stage.TRIAGE, reads.Stage.REVIEW])
@pytest.mark.parametrize("finished", [False, True])
def test_recorded_progress_survives_idle_standings(status, hold, stage, finished):
    t = ticket(1, status=status)
    v = view([t], starts=[] if hold is None else [shown.Start(t.number, hold)])
    v = replace(v, work={t.number: [reads.Work(100, stage, finished)]})
    root = ET.fromstring(dashboard.queued(v, standings.Standings(v)).replace(" open>", ' open="">'))
    row = element(root, f".//div[@data-n='{t.number}']")
    bar = row.find(".//span[@class='mb']")
    assert bar is not None
    assert bar.findall("b")[stage].get("class") == ("d" if finished else "x")


def test_triage_log_progress_survives_waiting_on_a_new_draft():
    draft = ticket(2, kind=Kind.CHANGE, status=Status.DRAFT)
    t = ticket(1, status=Status.WAITING, log=(
        LogLine(1, Status.NEW, "coordinator", None, "filed", False, None, False, None, None, None),
        LogLine(50, Status.WAITING, "ticket-analyst", None, "waiting", False,
                draft.number, True, None, None, None),))
    untouched = ticket(3, log=(t.log[0],))
    v = view([t, draft, untouched])
    st = standings.Standings(v)
    root = ET.fromstring(dashboard.queued(v, st))
    assert root.find(f".//div[@data-n='{t.number}']//b[@class='d']") is not None
    assert root.find(f".//div[@data-n='{untouched.number}']//span[@class='mb']") is None


@pytest.mark.parametrize("working", [False, True])
def test_expedited_bundle_precedes_routine_work(working):
    routine = ticket(1)
    request = ticket(2, filer="ticket-analyst")
    change = ticket(3, kind=Kind.CHANGE, filer="ticket-analyst", motivation=(request.number,))
    agents = [shown.ShownAgent(Role.CODE_EDITOR, 990, (routine.number, change.number))] if working else []
    v = view([routine, request, change], agents=agents,
             starts=[shown.Start(routine.number, None), shown.Start(change.number, None)])
    v = replace(v, expedited=frozenset({request.number}))
    st = standings.Standings(v)
    text = dashboard.active(v, st)[0] if working else dashboard.queued(v, st)
    root = ET.fromstring(text)
    rows = [r.get("data-n") for r in root.iter("div") if "wr" in r.get("class", "").split()]
    assert rows == [request.number, routine.number]


@pytest.mark.parametrize("count", [2, 3, 5])
@pytest.mark.parametrize("working", [False, True])
def test_bundle_title_members_stage_and_fold(count, working):
    requests = [ticket(n, kind=Kind.REQUEST, goal=f"Request goal {n}") for n in range(1, count + 1)]
    change = ticket(20, kind=Kind.CHANGE, status=Status.ASSIGNED,
                    title="dashboard: serve every request, including later ones",
                    motivation=tuple(t.number for t in requests) + (requests[0].number,))
    # Reach the first request twice, through Motivation and the waiting log.
    requests[0] = replace(requests[0], status=Status.WAITING, log=(
        LogLine(50, Status.WAITING, "operator", None, "waiting", False,
                change.number, True, None, None, None),))
    agents = [shown.ShownAgent(Role.CODE_REVIEWER, 990, (change.number,))] if working else []
    v = view([*requests, change], agents=agents, starts=[shown.Start(change.number, None)])
    v = replace(v, work={change.number: [reads.Work(100, reads.Stage.BUILD, True)]})
    st = standings.Standings(v)
    assert len(st.rows) == 1
    html = dashboard.active(v, st)[0] if working else dashboard.queued(v, st)
    root = ET.fromstring(html)
    row = root.find(f".//div[@data-n='{change.number}']")
    assert row is not None
    assert element(row, "./span[@class='wp']").text == change.title
    members = element(row, "./div[@class='members']")
    links = members.findall(".//a")
    assert [(a.get("data-n"), a.text) for a in links] == [
        (t.number, f"{t.number} · {t.goal}") for t in requests]
    assert len(members.findall("./a")) == min(3, count)
    fold = members.find("details")
    if count > 3:
        assert fold is not None and "open" not in fold.attrib
        assert element(fold, "summary").text == f"+{count - 3} more"
    else:
        assert fold is None
    if working:
        assert "Review ·" in "".join(element(row, "./span[@class='ws']").itertext())
        assert row.find(".//b[@class='n']") is not None
    else:
        assert row.find(".//b[@class='d']") is not None


def test_single_request_keeps_its_row_form():
    request = ticket(1, kind=Kind.REQUEST, goal="The original goal")
    change = ticket(2, kind=Kind.CHANGE, motivation=(request.number,))
    v = view([request, change], agents=[shown.ShownAgent(Role.CODE_EDITOR, 990, (change.number,))])
    root = ET.fromstring(dashboard.active(v, standings.Standings(v))[0])
    row = element(root, f".//div[@data-n='{request.number}']")
    assert element(row, "./span[@class='wp']").text == request.goal
    assert element(row, "./span[@class='wn']/small/a").get("data-n") == change.number


def test_bundle_folds_members_after_three():
    requests = [ticket(n, kind=Kind.REQUEST, goal=f"Goal {n}") for n in range(1, 5)]
    bug = ticket(5)
    change = ticket(6, kind=Kind.CHANGE, motivation=tuple(t.number for t in [*requests, bug]))
    v = view([*requests, bug, change])
    root = ET.fromstring(dashboard.queued(v, standings.Standings(v)))
    members = element(root, ".//div[@class='members']")
    assert [a.get("data-n") for a in members.findall("./a")] == [
        requests[0].number, requests[1].number, requests[2].number]
    assert element(members, "./details/summary").text == "+2 more"
    assert [a.get("data-n") for a in members.findall("./details/a")] == [requests[3].number, bug.number]


def test_a_log_line_appended_to_a_ticket_changes_the_fingerprint(tmp_path: Path, monkeypatch) -> None:
    module = script("ticket_dashboard")
    monkeypatch.setattr(module, "CODEX", module.CodexLimits(tmp_path))
    path = tmp_path / "new" / "9-1_bug_x_coordinator.md"
    path.parent.mkdir()
    path.write_text("---\nkind: bug\n---\n# x: y\n\n## Log\n2026-10-19T00:00:00Z new [coordinator]: filed\n")
    before = module.fingerprint(tmp_path)
    with path.open("a") as f:
        f.write("2026-10-19T00:01:00Z new [coordinator]: note\n")
    assert module.fingerprint(tmp_path) != before
