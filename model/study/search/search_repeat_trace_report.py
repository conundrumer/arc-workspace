#!/usr/bin/env python3
"""Counts repeated clause texts in the SEARCH_TRACE=2 logs of a search-repeat-trace run.

    python3 -I search_repeat_trace_report.py RUN_FOLDER [--check ARM/TASK]

RUN_FOLDER holds manifest.json and out/<arm>/<task>/work/*.log. The logs may still be written:
a last line with no newline is dropped, and tries after the last `visit` line are kept as an
open visit whose slot is unknown. Uses the standard library only. Reads files, writes none.

What a log holds (superdag_search.py, visit):
  "    <out> <clause text[:300]>"    one per try, out is new, equal or none
  "  visit N: M forms KIND, T tries, ..., end WHY: <one char per try>"   ends a visit
      N counts the visits of that slot (a slot is one scope and kind; it keeps the count across
      generations), M is the number of forms in the scope. The char is N new, x none,
      e equal with a clause that reads a scope form, f equal with a clause that reads none.
  "generation N: ..."   starts a process.
  "prof {...}"          has the counters `draws` and `equal`.

Same clause: the two clause texts have the same clause_key (see below): the kind and the atoms, with no head name, the same
for any order of the atoms and any names of the labels.
A text is unparsed when it is cut at 300 characters (the log keeps 300 characters of a clause text): it has unbalanced
parentheses, so it has no key. Unparsed texts are counted apart (class `unparsed`) and never match. Shares come as a range: low counts the sure repeats, high counts the sure repeats and the unparsed tries.
"""
import functools
import json
import os
import re
import sys
import zlib
from collections import Counter

CUT = 300
TOKEN = re.compile(r'\(|\)|[^\s()]+')
TRY = re.compile(r'^    (new|equal|none) (.*)$')
VISIT = re.compile(r'^  visit (\d+): (\d+) forms (\w+), (\d+) tries, (\d+) new, ([0-9.]+) s, end (\w+): ([A-Za-z]*)$')
GEN = re.compile(r'^generation (\d+): rss (\d+) after load, (\d+) forms')
PROF = re.compile(r'^prof (\{.*\})$')
RSS_AT = re.compile(r'^rss (\d+) at (\d+) s of (\d+), cpu (\d+) s, (\d+) samples')
HEAD = re.compile(r'^\((RULE|DET|INIT) &[rf]\d+')
FORM = re.compile(r'&f\d+')
KNOWN_START = ('rss ', 'manager', 'pool clauses', 'end:', '{', 'bank file', 'prof ', 'generation ', 'the bank alone')
KINDS = ('RULE', 'DET', 'INIT')
TP = ('tp_visit', 'tp_slot', 'tp_other', 'tp_unres')
OP = ('op_slot', 'op_other', 'op_unres')
SURE = TP + OP


# ---- clause_key ------------------------------------------------------------------------------
# parse, flat, draw, atoms_key, _key and clause_key are copied unchanged from
# kit44/model/study/sampler/search.py (section "a clause as a key"). That file imports `live`, which needs the engine,
# so the functions are copied here. TOKEN is the same pattern as TOKEN in that file.

def parse(text):
    """The s-expression of text as nested lists of strings."""
    stack = [[]]
    for t in TOKEN.findall(text):
        if t == '(':
            stack.append([])
        elif t == ')':
            top = stack.pop()
            stack[-1].append(top)
        else:
            stack[-1].append(t)
    return stack[0]


def flat(x):
    for y in x:
        if isinstance(y, list):
            yield from flat(y)
        else:
            yield y


def draw(x, color, mark=None):
    """x as a string: a label by its color, and the label mark as '@'. The children of a node that are all lists, as the sites of an
    atom or the atoms of a branch, are in sorted order."""
    if isinstance(x, str):
        s = x.lstrip('*')
        if s in color:
            return '@' if s == mark else '#%d' % color[s]
        return x
    parts = [draw(y, color, mark) for y in x]
    if parts and all(isinstance(y, list) for y in x):
        parts.sort()
    elif len(x) > 1 and isinstance(x[0], str) and all(isinstance(y, list) for y in x[1:]):
        parts = parts[:1] + sorted(parts[1:])
    return '(' + ' '.join(parts) + ')'


def atoms_key(atoms):
    """A hashable key of atoms, the texts or parsed atoms of a conjunction: the same for any order of the atoms and any names of the
    labels (a label is a name that a '*' marks once at least). The labels get colors by refining the multiset of the atoms around
    each; two labels with the same neighbours get one color, so the key can be the same for clauses that differ."""
    parsed = [x if isinstance(x, list) else (parse(x) or [[]])[0] for x in atoms]
    labels = {t[1:] for a in parsed for t in flat(a) if t.startswith('*') and len(t) > 1}
    color = dict.fromkeys(labels, 0)
    where = {l: [a for a in parsed if any(t.lstrip('*') == l for t in flat(a))] for l in labels}
    for _ in range(3):
        color = {l: zlib.crc32('\x1f'.join(sorted(draw(a, color, l) for a in where[l])).encode()) for l in labels}
    return tuple(sorted(draw(a, color) for a in parsed))


@functools.lru_cache(maxsize=1 << 12)
def _key(text):
    forms = parse(text)
    if not forms or not forms[0]:
        return ()
    form = forms[0]
    return (form[0],) + atoms_key(form[2:])


def clause_key(text):
    """A key of the clause text, a form such as (RULE &head atom ...): its kind and atoms, with no head name; the same for any order
    of the atoms and any names of the labels."""
    return _key(text)


def balanced(text):
    """True when the parentheses of text close: a text cut at 300 characters does not."""
    depth = 0
    for ch in text:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def read_lines(path):
    """The complete lines of a file that may still grow, and the incomplete last line if any."""
    with open(path, 'rb') as f:
        text = f.read().decode('utf-8', errors='replace')
    lines = text.split('\n')
    last = lines.pop()
    return lines, (last or None)


class Log:
    def __init__(self, arm, task, path):
        self.arm, self.task, self.path = arm, task, path
        self.cnt = Counter()          # (kind, outcome, cls, cut, free) -> tries
        self.notes = Counter()        # things that look wrong
        self.examples = {}            # note -> first line number
        self.exact = {}               # clause_key -> [(gen, vid, slot)]
        self.slots = {}               # (kind, n forms) -> [slot]
        self.all_slots = []
        self.nslot = 0
        self.vid = 0
        self.gens = 0
        self.gen = -1
        self.tries = Counter()        # outcome -> tries
        self.visits = 0
        self.open_tries = 0
        self.partial = None
        self.last_rss = None          # (t, budget, gen)
        self.last_prof = None
        self.check = []               # prof rows
        self.visit_slot = Counter()   # how a visit's slot was found
        self.sup_status = None

    def note(self, what, ln=None):
        self.notes[what] += 1
        if ln is not None and what not in self.examples:
            self.examples[what] = ln

    # ---- slot of a visit -------------------------------------------------------------
    def top_slot(self):
        """The live slot with the highest last rate, when the rates (new/secs, secs rounded to 0.1) tell it for sure, else None.
        next_slot resumes max(live parked slots, key=last rate). A live slot is not exhausted and had a new node in its last visit."""
        best, best_lo, others = None, -1.0, []
        for s in self.all_slots:
            if s['exh'] or s['new'] <= 0:
                continue
            lo = s['new'] / (s['secs'] + 0.05)
            hi = s['new'] / max(s['secs'] - 0.05, 1e-3)
            others.append((s, lo, hi))
            if lo > best_lo:
                best, best_lo = s, lo
        if best is None:
            return None
        for s, lo, hi in others:
            if s is not best and hi >= best_lo:
                return None
        return best

    def ids_of(self, s, kind, n):
        """The slot ids that this slot may stand for: itself, or the tainted slots of its kind and size."""
        if not s['taint']:
            return frozenset((s['id'],))
        return frozenset(x['id'] for x in self.slots[(kind, n)] if x['taint'])

    def find_slot(self, kind, n, k, new, secs, end):
        """Gives the set of slot ids that the visit line may stand for (one id when it can tell), or None."""
        lst = self.slots.setdefault((kind, n), [])
        if k == 1:
            self.nslot += 1
            s = {'id': self.nslot, 'v': 1, 'taint': False, 'new': new, 'secs': secs, 'exh': end == 'exhausted'}
            lst.append(s)
            self.all_slots.append(s)
            self.visit_slot['new slot'] += 1
            return frozenset((s['id'],))
        cands = [s for s in lst if s['v'] == k - 1]
        top = self.top_slot()
        chosen, how = None, None
        if top is not None and top in cands:
            chosen, how = top, 'resume, the highest-rate slot fits the line'
        elif len(cands) == 1:
            chosen = cands[0]
            if top is None:
                how = 'resume or repeat pick, one slot fits'
            else:
                how = 'repeat pick (the highest-rate slot does not fit), one slot fits'
        elif len(cands) > 1:
            for s in cands:
                s['taint'] = True
            chosen = cands[0]
            how = 'several slots fit, line cannot tell'
            result = frozenset(s['id'] for s in cands)
        else:
            self.visit_slot['no slot fits (state off)'] += 1
            return None
        if how != 'several slots fit, line cannot tell':
            result = self.ids_of(chosen, kind, n)
        self.visit_slot[how] += 1
        chosen['v'] = k
        chosen['new'], chosen['secs'], chosen['exh'] = new, secs, end == 'exhausted'
        return result

    # ---- one try -----------------------------------------------------------------------
    @staticmethod
    def relate(a, b):
        if a is None or b is None:
            return 'unres'
        if len(a) == 1 and a == b:
            return 'same'
        if a.isdisjoint(b):
            return 'other'
        return 'unres'

    def classify(self, K, cut, cur):
        """K is the clause_key, or None when the text is unparsed."""
        if K is None:
            return 'unparsed'
        sure = self.exact.get(K, [])
        maybe = []
        if sure:
            same = [o for o in sure if o[0] == cur[0]]
            group, pre = (same, 'tp') if same else (sure, 'op')
            if pre == 'tp' and any(o[1] == cur[1] for o in group):
                return 'tp_visit'
            rel = [self.relate(o[2], cur[2]) for o in group]
            if 'same' in rel:
                return pre + '_slot'
            if 'unres' in rel:
                return pre + '_unres'
            return pre + '_other'
        return 'diff'

    def add_try(self, outcome, raw, trace_ch, cur, ln):
        m = HEAD.match(raw)
        if m:
            kind = m.group(1)
        else:
            kind = '?'
            self.note('clause text without a kind and head', ln)
        K = clause_key(raw) if balanced(raw) else None
        if K == ():
            K = None
        if K is not None and kind != '?' and K[0] != kind:
            self.note('clause key kind differs from the head kind', ln)
        cut = len(raw) >= CUT
        regex_free = not FORM.search(raw)
        if trace_ch in ('e', 'f'):
            free = trace_ch == 'f'
            if not cut and free != regex_free:
                self.note('trace char e/f disagrees with the &f test', ln)
        else:
            free = regex_free
        cls = self.classify(K, cut, cur)
        self.cnt[(kind, outcome, cls, cut, free)] += 1
        if K is not None:
            self.exact.setdefault(K, []).append(cur)
        else:
            self.notes['text with no key (unparsed)'] += 1
            self.examples.setdefault('text with no key (unparsed)', ln)
        return kind

    def flush(self, pending, vinfo, ln):
        """pending: [(outcome, raw, line number)]. vinfo: the visit line's fields, or None."""
        self.vid += 1
        if vinfo is None:
            slot, trace = None, None
            self.visit_slot['no visit line'] += 1
        else:
            k, n, vkind, tries, trace, vnew, vsecs, vend = vinfo
            slot = self.find_slot(vkind, n, k, vnew, vsecs, vend)
            if tries != len(pending):
                self.note('visit line tries differ from try lines', ln)
            if len(trace) != tries:
                self.note('visit line trace length differs from its tries', ln)
            self.visits += 1
        cur = (self.gen, self.vid, slot)
        for i, (outcome, raw, tln) in enumerate(pending):
            ch = trace[i] if trace is not None and i < len(trace) else None
            if ch is not None and {'N': 'new', 'x': 'none', 'e': 'equal', 'f': 'equal'}.get(ch) != outcome:
                self.note('trace char does not fit the try outcome', tln)
                ch = None
            kind = self.add_try(outcome, raw, ch, cur, tln)
            if vinfo is not None and kind != vinfo[2]:
                self.note('clause kind differs from the visit line kind', tln)
            self.tries[outcome] += 1

    # ---- the file ------------------------------------------------------------------------
    def read(self):
        lines, self.partial = read_lines(self.path)
        pending, tries_all, eq_all, eq_gen = [], 0, 0, 0
        for ln, line in enumerate(lines, 1):
            m = TRY.match(line)
            if m:
                pending.append((m.group(1), m.group(2), ln))
                tries_all += 1
                if m.group(1) == 'equal':
                    eq_all += 1
                    eq_gen += 1
                continue
            m = VISIT.match(line)
            if m:
                trace = m.group(8)
                self.flush(pending, (int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)), trace, int(m.group(5)), float(m.group(6)), m.group(7)), ln)
                pending = []
                continue
            m = GEN.match(line)
            if m:
                if pending:
                    self.note('tries with no visit line before a generation line', ln)
                    self.flush(pending, None, ln)
                    pending = []
                self.gen = int(m.group(1))
                self.gens += 1
                eq_gen = 0
                continue
            m = PROF.match(line)
            if m:
                try:
                    p = json.loads(m.group(1))
                except ValueError:
                    self.note('prof line is not JSON', ln)
                    continue
                if pending:
                    self.note('prof line inside a visit', ln)
                self.last_prof = p
                self.check.append((p.get('gen'), p.get('t'), p.get('draws'), tries_all, p.get('equal'), eq_gen, eq_all))
                continue
            m = RSS_AT.match(line)
            if m:
                self.last_rss = (int(m.group(2)), int(m.group(3)), self.gen)
                continue
            if line.startswith('    '):
                self.note('indented line that is not a try', ln)
            elif not line.startswith(KNOWN_START) and ' tries/s, ' not in line:
                self.note('other line: ' + line[:40], ln)
        if pending:
            self.open_tries = len(pending)
            self.flush(pending, None, len(lines))


# ---- sums and printing -----------------------------------------------------------------------

def agg(logs, arm=None, task=None, kind=None, outcome=None, free=None):
    c = Counter()
    for L in logs:
        if (arm and L.arm != arm) or (task and L.task != task):
            continue
        for (k, o, cls, cut, fr), n in L.cnt.items():
            if (kind and k != kind) or (outcome and o != outcome) or (free is not None and fr != free):
                continue
            c[cls] += n
            c['_n'] += n
            if cut:
                c['_cut'] += n
    return c


def sure_n(c, which=SURE):
    return sum(c[k] for k in which)


def pct(x, n):
    return '%5.1f' % (100.0 * x / n) if n else '    -'


def rng(lo, hi, n):
    return '%5.1f-%5.1f' % (100.0 * lo / n, 100.0 * hi / n) if n else '     -     '


GROUPS = (('both', None), ('base', 'base'), ('evict', 'evict'))
KROWS = (('all', None),) + tuple((k, k) for k in KINDS)


def outcome_table(logs, outcome, out):
    out.append('%-6s %-5s %6s %5s | %-11s | %5s %5s %5s %5s | %5s %5s %5s | %5s | %-11s' % (
        'arm', 'kind', 'tries', 'cut', 'same % lo-hi', 'visit', 'slot', 'other', 'unres', 'slot', 'other', 'unres', 'unpar', 'differ % hi-lo'))
    out.append('%-6s %-5s %6s %5s | %-11s | %-23s | %-17s | %5s | %-11s' % (
        '', '', '', '', '', 'same process, % of tries', 'older process, %', '(cut)', ''))
    for gname, arm in GROUPS:
        for kname, kind in KROWS:
            c = agg(logs, arm=arm, kind=kind, outcome=outcome)
            n = c['_n']
            sure, maybe = sure_n(c), c['unparsed']
            out.append('%-6s %-5s %6d %5d | %s | %s %s %s %s | %s %s %s | %s | %s' % (
                gname, kname, n, c['_cut'], rng(sure, sure + maybe, n),
                pct(c['tp_visit'], n), pct(c['tp_slot'], n), pct(c['tp_other'], n), pct(c['tp_unres'], n),
                pct(c['op_slot'], n), pct(c['op_other'], n), pct(c['op_unres'], n),
                pct(maybe, n), rng(n - sure - maybe, n - sure, n)))
        out.append('')


def distinct_table(logs, out):
    out.append('%-6s %-5s %7s %7s | %-13s | %s' % ('arm', 'kind', 'tries', 'cut', 'distinct/try', 'distinct texts lo-hi'))
    for gname, arm in GROUPS:
        for kname, kind in KROWS:
            c = agg(logs, arm=arm, kind=kind)
            n = c['_n']
            sure, maybe = sure_n(c), c['unparsed']
            out.append('%-6s %-5s %7d %7d | %5.3f-%5.3f   | %d-%d' % (
                gname, kname, n, c['_cut'], (n - sure - maybe) / n if n else 0, (n - sure) / n if n else 0, n - sure - maybe, n - sure))
    out.append('')


def bar_table(logs, bar, out):
    out.append('Same-clause share of equal tries (a fraction, not %%). Bar %.2f. lo = sure repeats, hi = sure + unparsed.' % bar)
    out.append('Any = an earlier try of that text anywhere in the task log. Same process = in the same process only.')
    out.append('%-6s %-5s %6s | %-13s | %-13s | %s' % ('arm', 'kind', 'equal', 'any lo-hi', 'same proc', 'against the bar (any)'))
    for gname, arm in GROUPS:
        for kname, kind in KROWS:
            c = agg(logs, arm=arm, kind=kind, outcome='equal')
            n = c['_n']
            sure, maybe, tp = sure_n(c), c['unparsed'], sure_n(c, TP)
            if n:
                lo, hi = sure / n, (sure + maybe) / n
                verdict = 'at or above' if lo >= bar else ('below' if hi < bar else 'range holds the bar')
                out.append('%-6s %-5s %6d | %.3f-%.3f   | %.3f-%.3f   | %s' % (gname, kname, n, lo, hi, tp / n, (tp + maybe) / n, verdict))
    out.append('')
    out.append('Equal tries by whether the clause reads a scope form (trace char f = reads none, e = reads one):')
    out.append('%-6s %-12s %6s %6s | %-13s' % ('arm', 'clause', 'equal', 'share', 'same lo-hi'))
    for gname, arm in GROUPS:
        tot = agg(logs, arm=arm, outcome='equal')['_n']
        for label, fr in (('reads none', True), ('reads scope', False)):
            c = agg(logs, arm=arm, outcome='equal', free=fr)
            n = c['_n']
            sure, maybe = sure_n(c), c['unparsed']
            if n:
                out.append('%-6s %-12s %6d %5.1f%% | %.3f-%.3f' % (gname, label, n, 100.0 * n / tot, sure / n, (sure + maybe) / n))
    out.append('')
    out.append('Per task (equal tries, same-clause share lo-hi, any earlier try):')
    out.append('%-6s %-9s %6s | %-13s | %s' % ('arm', 'task', 'equal', 'share', 'tries'))
    for L in logs:
        c = agg([L], outcome='equal')
        n = c['_n']
        sure, maybe = sure_n(c), c['unparsed']
        if n:
            out.append('%-6s %-9s %6d | %.3f-%.3f   | %d' % (L.arm, L.task, n, sure / n, (sure + maybe) / n, sum(L.tries.values())))
    out.append('')


def progress_table(logs, budget, out):
    out.append('%-6s %-9s %4s %6s %6s %7s %10s %10s %s' % ('arm', 'task', 'gens', 'visits', 'tries', 'open', 'prof t,gen', 'est. wall s', 'supervisor last status'))
    for L in logs:
        p = L.last_prof or {}
        est = '-'
        if L.last_rss:
            t, b, _ = L.last_rss
            est = '%d' % (budget - b + t)
        out.append('%-6s %-9s %4d %6d %6d %7d %6s,%-3s %10s %s' % (
            L.arm, L.task, L.gens, L.visits, sum(L.tries.values()), L.open_tries,
            p.get('t', '-'), p.get('gen', '-'), est, L.sup_status or '-'))
    out.append('')


def check_table(logs, which, out):
    exact_d = tot_d = exact_e = tot_e = 0
    for L in logs:
        for gen, t, draws, tr, eq, eq_gen, eq_all in L.check:
            tot_d += 1
            exact_d += draws == tr
            tot_e += 1
            exact_e += eq == eq_gen
    out.append('All logs: prof lines with draws equal to the try lines before them: %d of %d. prof equal equal to the equal try lines of the same process: %d of %d.' % (exact_d, tot_d, exact_e, tot_e))
    L = next((x for x in logs if '%s/%s' % (x.arm, x.task) == which), None)
    if L is None:
        out.append('No log %s for the detail check.' % which)
        return
    out.append('Detail for %s/%s (%d generations). Trace columns count the try lines before the prof line.' % (L.arm, L.task, L.gens))
    out.append('%4s %7s %8s %8s %6s | %8s %10s %8s' % ('gen', 'prof t', 'draws', 'tries', 'diff', 'equal', 'trace eq', 'diff'))
    for gen, t, draws, tr, eq, eq_gen, eq_all in L.check:
        out.append('%4s %7s %8s %8d %6s | %8s %10d %8s' % (gen, t, draws, tr, (draws - tr) if draws is not None else '-', eq, eq_gen, (eq - eq_gen) if eq is not None else '-'))
    out.append('')


def sup_last(path):
    try:
        with open(path) as f:
            lines = [x for x in f.read().split('\n') if 'status at' in x]
    except OSError:
        return None
    if not lines:
        return None
    m = re.match(r'(\S+) status at (\d+) s: running (\d+).*?done (\d+)', lines[-1])
    return '%s at %s s, running %s done %s' % (m.group(1), m.group(2), m.group(3), m.group(4)) if m else lines[-1][:60]


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    run = argv[0]
    which = None
    if '--check' in argv:
        which = argv[argv.index('--check') + 1]
    with open(os.path.join(run, 'manifest.json')) as f:
        man = json.load(f)
    arms_dirs = sorted(os.listdir(os.path.join(run, 'out')))
    bar_m = re.search(r'(\d\.\d+) or more', man.get('bar', ''))
    bar = float(bar_m.group(1)) if bar_m else 0.35
    bud_m = re.match(r'(\d+)', man.get('budget', ''))
    budget = int(bud_m.group(1)) if bud_m else 600
    logs = []
    for arm in arms_dirs:
        tasks = sorted(os.listdir(os.path.join(run, 'out', arm)))
        for task in tasks:
            wd = os.path.join(run, 'out', arm, task, 'work')
            if not os.path.isdir(wd):
                continue
            for name in sorted(os.listdir(wd)):
                if name.endswith('.log'):
                    L = Log(arm, task, os.path.join(wd, name))
                    L.sup_status = sup_last(os.path.join(run, 'out', arm, task, 'supervisor.log'))
                    L.read()
                    logs.append(L)
    if which is None:
        which = next(('%s/%s' % (L.arm, L.task) for L in logs if L.arm == 'evict' and L.gens == 1), '')
    out = []
    out.append('Run %s' % os.path.basename(os.path.normpath(run)))
    out.append('Manifest: arms %s, %s, budget %s' % (', '.join(arms_dirs), man.get('task_set'), man.get('budget')))
    out.append('Bar: %s' % man.get('bar'))
    out.append('')
    out.append('== How far the logs reach (est. wall s = budget - this process budget + this process t) ==')
    progress_table(logs, budget, out)
    out.append('== Tries of one outcome: how many repeat a clause text tried before in this task ==')
    out.append('Percent of that outcome\'s tries. "same" = a text tried before (sure or maybe, range). Columns split the sure ones:')
    out.append('same process = an earlier try in this process (visit = this visit, slot = an earlier visit of this slot, other = another slot,')
    out.append('unres = the visit line cannot tell the slot); older process = no earlier try in this process, only in an older one.')
    out.append('unparsed = the text is cut at 300 characters and has no key, so it matches nothing. differ = tries - same - unparsed.')
    out.append('')
    for outcome, label in (('equal', 'EQUAL (item 1)'), ('none', 'NONE (item 2)'), ('new', 'NEW (item 3; a repeat that gave a new table means keys were reset)')):
        out.append('-- %s --' % label)
        outcome_table(logs, outcome, out)
    out.append('== Distinct clause texts per try, all outcomes (item 4) ==')
    distinct_table(logs, out)
    out.append('== Same-clause share of equal against the bar (item 5) ==')
    bar_table(logs, bar, out)
    out.append('== Check against the prof lines ==')
    check_table(logs, which, out)
    out.append('== What the visit lines say about slots ==')
    vs = Counter()
    for L in logs:
        vs.update(L.visit_slot)
    for k, v in sorted(vs.items()):
        out.append('  %-28s %d' % (k, v))
    out.append('')
    out.append('== Things that look wrong in the logs ==')
    any_note = False
    for L in logs:
        for what, n in sorted(L.notes.items()):
            any_note = True
            out.append('  %s/%s: %s x%d (first at line %s)' % (L.arm, L.task, what, n, L.examples.get(what)))
        if L.partial is not None:
            any_note = True
            out.append('  %s/%s: last line has no newline yet, left out (%d characters)' % (L.arm, L.task, len(L.partial)))
    if not any_note:
        out.append('  none. (Tries after the last visit line are a visit still running: the "open" column above. They are counted with no slot.)')
    print('\n'.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
