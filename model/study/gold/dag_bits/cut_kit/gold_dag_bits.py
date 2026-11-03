"""Tool 1. The bits of each form of a stem with no read of written order: -log2 of the summed chance over the form's valid atom orders, with context from the forms that it reads. One stem's row goes to stdout after each pass of work; the last row is the stem's row. gold_dag_run.py runs many stems.

  <runtime python> gold_dag_bits.py TASK LINES.json [SECONDS]

LINES.json maps the stem to its forms.

Ports: the decoder offers an atom only a column past the last one written, in the column order of the table that the atom reads, so a port out of that order costs the walk, and that table's column order is set by the canonical body of the relation that the atom reads. `portsort` writes the ports of every atom in that order, over the canonical forms that the form reads, for each form of the canonical scope and for the target (whose atom order stays as written). Ports of a record and of an INIT's heads stay. A form whose ports cannot be matched with its tokens, or whose sorted text the reader refuses, keeps its ports (counts: 'forms whose ports do not match the tokens', 'forms whose sorted ports the reader refuses').
Context: the forms that the target reads, directly or not, in the order of sample2_col.ancestor_order (depth in the read graph, then form text), each in its canonical atom order (`canonical`), since a form's atom order sets its relation's column order. Row field `canon_kept` counts the forms that keep their written text. A form's scope replays on a fresh session and each walk is a fork of that replay, by gold_fork_reads.py, so each read is the read of a new session.
Orders: gold_dag_orders.py. An order is valid where the reader takes its text and the walk of live.py follows it with no `bad` and no `dead`. The chances of two orders with the same tokens count once.
Cap: a form whose guard rule gives at most CAP orders has every order tried, and its row has status `exact`. Another form has status `bound`: CAP orders are walked, SAMPLE_SHARE of them drawn at random with a seed of the form's sorted items, and the rest by swapping neighbours in the cheapest order so far, cheapest first. The sum over a subset of the orders is an upper bound on the bits. Up to 20 draws per walk go on orders that the reader refuses.
A walk stops at DELTA bits over the cheapest order so far, since such an order adds under 2^-DELTA of the sum: at most CAP 2^-DELTA, 0.003 bits at the defaults. Those walks count as `dropped`.
`bits` reads no written position: it sums only the orders of `every` or `sampled` (for status `one` the single order is the written walk). The written walk has its own fields and joins only `tight`; a form of status `written` shows its written figure as `bits`. A `bound` form can have `bits` over `written`.
Time: first every form's orders are counted (`sizes`, `orders`), then every form's written order walks. Then forms go worst first, and past SECONDS the rest keep the figure that they have, with status `written`.

Fields of a form's row: line, kind, nscope, sizes (items by site), orders (count by the guard rule, None past the count's reach), tried, refused, valid, dropped, status, bits, best (the cheapest order walked), written (bits of the written order on this context), tight (the same sum with the written order added, never over `written`), error (a form that could not be planned or walked: its figure is the written one), prefix (bits of the written order over all earlier written forms, the figure of the cut stages).
status: `exact`, `bound`, `written` as above; `one` for a form with a single order; `none` where no order has bits; `no draw` for a kind that the walk does not draw. A form with status `none` or `no draw` has bits null; a form of status `none` has `partial`, the bits of its written order's walk before its first refused choice.
"""
import hashlib, heapq, itertools, json, math, os, re, sys, time
import gold_fork_reads as F
from gold_fork_reads import OVER, counts, load_sampler, timed, times
import arclog, live
from gold_chain import parse, show
from gold_dag_orders import Body, Orders, lse2, rng_of

CAP = int(os.environ.get('DAG_ORDER_CAP', 120))
DELTA = float(os.environ.get('DAG_DELTA', 16))
SAMPLE_SHARE = 0.5
CANON_TRIES = 3000
CANON_MEMO = {}  # (form text, canonical scope) -> its canonical text, or None; the reader's answer does not change in a process
DRAWS = 20  # reader refusals per walk of a sampled form
EVERY = 20.0  # seconds between rows
task = base_lines = t0 = SECONDS = None


def setup(stem, lines_path, seconds=840):
    global task, base_lines, t0, SECONDS
    task, SECONDS = stem, float(seconds)
    base_lines = [x for x in json.load(open(lines_path))[task] if x.strip()]
    t0 = time.time()
    F.begin(task)


def takes(lines):
    """Whether the reader takes the forms."""
    try:
        arclog.StudyProgram.from_sexp('\n'.join((*lines, live.READER_OUT)), F.OS.settings).decode_stream()
        return True
    except Exception:  # noqa: BLE001
        return False


_VOCAB = {}


def vocabulary():
    if F.task not in _VOCAB:
        import live_try
        _VOCAB[F.task] = live_try.session_of(F.task)[0].vocabulary
    return _VOCAB[F.task]


def is_port(x):
    return isinstance(x, list) and bool(x) and isinstance(x[0], str) and x[0].startswith(':')


def column_layout(scope, text):
    """[(column, fields)] for the ports of text over scope, in the order of the model tokens. For a record-valued port, fields is the list of its fields' columns in token order (None where a field holds a record of its own). Otherwise fields is None."""
    V = vocabulary()
    ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), F.OS.settings).decode_stream()
    toks = [(V.name(int(x)), V.kind(int(x))) for x, m, p in zip(ids, model, paths) if m and p[0] == len(scope)]
    out, k = [], 0
    while k < len(toks):
        name, kind = toks[k]
        k += 1
        if kind != 'column':
            continue
        fields = None
        if k < len(toks) and toks[k][1] == 'column':  # a record-valued port: its fields' columns run to the END
            fields = []
            while k < len(toks) and toks[k][0] != 'END':
                if toks[k][1] == 'column':
                    fields.append(int(toks[k][0][1:]))
                    if k + 1 < len(toks) and toks[k + 1][1] == 'column':  # a record inside a field
                        fields = None
                        while k < len(toks) and toks[k][0] != 'END':
                            k += 1
                        break
                k += 1
        out.append((int(name[1:]), fields))
    return out


def column_positions(scope, text):
    """The column positions of the ports of text over scope, in the order of the model tokens: the position of each port of the table that the atom reads."""
    return [c for c, _ in column_layout(scope, text)]


def ports_in_order(scope, text):
    """text with the ports of each atom in the column order of the relation that the atom reads. The decoder offers only a column past the last one written, so a port out of that order costs the walk, and the table's column order is set by the relation's own canonical body. The fields of a record port go in the column order of the record's key, and the ports of an INIT's heads stay. Marks of a RULE or DET are moved to the first occurrence of the label. Returns text where the ports cannot be matched with the tokens, or where the reader refuses the new text."""
    form = parse(text)
    slots = []

    def walk(x):
        atom = bool(x) and isinstance(x[0], str) and not x[0].startswith(':')  # a list with a name for its head: the ports under it are the atom's own
        for y in x:
            if isinstance(y, list):
                if atom and is_port(y):
                    slots.append(y)
                walk(y)
    walk(form)
    layout = column_layout(scope, text)
    pos = [c for c, _ in layout]
    if len(pos) != len(slots):
        counts['forms whose ports do not match the tokens'] += 1
        return text
    at = {id(y): p for y, p in zip(slots, pos)}
    for y, (_, fields) in zip(slots, layout):  # the fields of a record go in the column order of the record's key: the decoder offers a field only past the last one written
        if fields is None:
            continue
        if len(fields) == len(y) - 1:
            y[1:] = [z for _, z in sorted(zip(fields, y[1:]), key=lambda t: t[0])]
        else:
            counts['records whose fields do not match the tokens'] += 1

    def sort(x):
        for y in x:
            if isinstance(y, list):
                sort(y)
        if x and isinstance(x[0], str) and not x[0].startswith(':'):
            ks = [k for k, y in enumerate(x) if is_port(y)]
            if len(ks) > 1:
                got = sorted((x[k] for k in ks), key=lambda y: at[id(y)])
                for k, y in zip(ks, got):
                    x[k] = y
    sort(form)
    if form[0] in ('RULE', 'DET') and all(isinstance(a, list) for a in form[2:]):
        form[2:] = Body(list(form[2:])).reordered(tuple(range(len(form) - 2)))
    new = show(form)
    if new == text:
        return text
    counts['forms with ports moved'] += 1
    return new


PORTS_MEMO = {}


def portsort(scope, text):
    """ports_in_order, or text where that fails; one answer per (scope, text) in a process."""
    key = (tuple(scope), text)
    if key not in PORTS_MEMO:
        try:
            new = ports_in_order(scope, text)
            if new != text and not takes((*scope, new)):
                counts['forms whose sorted ports the reader refuses'] += 1
                new = text
        except Exception:  # noqa: BLE001
            counts['forms whose ports are not read'] += 1
            new = text
        PORTS_MEMO[key] = new
    return PORTS_MEMO[key]


ADVANCE_MEMO = {}  # (scope, text) -> whether the sampler's advance takes text as the next scope form
CANON_ADVANCES = int(os.environ.get('DAG_CANON_ADVANCES', 60))  # advance checks per form in canonical


def advances(scope, text):
    """Whether the sampler takes text as a scope form after scope. `takes` runs the reader only; the sampler's advance also runs the grammar's static prune ("the completed atom repeats an existing test"), and a form that it refuses leaves every reader of the form with no bits."""
    key = (tuple(scope), text)
    if key not in ADVANCE_MEMO:
        try:
            gs, _, _ = F.groups('\n'.join((*scope, text, live.READER_OUT)), F.OS.settings)
            gs0, keys0, _ = F.groups('\n'.join((*scope, live.READER_OUT)), F.OS.settings) if scope else ([], [], {})
            node = F.scope_node(gs0[:len(scope)], keys0[:len(scope)])
            _, c = F.OS.ask(node, 'advance', gs[len(scope)])
            c.close()
            ADVANCE_MEMO[key] = True
        except Exception:  # noqa: BLE001
            ADVANCE_MEMO[key] = False
    return ADVANCE_MEMO[key]


def canonical(ls):
    """The forms of ls in the order that reads no written position, and the count of forms that keep their written atom order. A form's atom order sets the column order of its relation, and each reader of the relation pays for a port out of that order, so a scope replays forms in this order. Forms go deepest last. For each form: its ports go in the column order of the relations that it reads, over the canonical forms it reads (portsort); then the first atom order, with items sorted by text, that the reader takes and the sampler advances over that scope. CANON_TRIES orders are tried per form, and CANON_ADVANCES of them reach the sampler. A form with no such order keeps its written atom order."""
    parsed = live.S.strata.sexprs('\n'.join(ls))
    out, kept = list(ls), 0
    todo = [i for i in form_lines(ls) if ls[i].startswith(tuple('(%s ' % k for k in live.KIND_TOK))]
    anc = {i: live.S.ancestor_order(parsed, i) for i in todo}  # the read graph does not move with atom order
    for i in sorted(todo, key=lambda i: (len(anc[i]), i)):
        scope = [out[j] for j in live.S.ancestor_order(parsed, i)]  # ancestors are done: they have fewer ancestors
        key = (ls[i], tuple(scope))
        if key not in CANON_MEMO:
            base = portsort(scope, ls[i])
            got = None
            try:
                o = Orders(base)
                if o.bodies:
                    tried = 0
                    for x in itertools.islice(o.every(), CANON_TRIES):
                        y = o.render(x)
                        if takes((*scope, y)):
                            tried += 1
                            if y == base or advances(scope, y):  # the written order of a gold form is one that the sampler takes
                                got = y
                                break
                            if tried >= CANON_ADVANCES:
                                break
                    CANON_MEMO[key] = (got, True) if got is not None else (base, advances(scope, base))
                else:
                    CANON_MEMO[key] = (base, True)
            except Exception:  # noqa: BLE001
                CANON_MEMO[key] = (base, False)
        y, ok = CANON_MEMO[key]
        kept += not ok
        out[i] = y
        parsed[i] = live.S.strata.sexprs(y)[0]
    return out, kept


def scope_of(ls, i):
    """The forms that form i reads: ls holds them in their canonical atom order, and ancestor_order sorts them by depth, then by that text."""
    forms = live.S.strata.sexprs('\n'.join(ls))
    return [ls[j] for j in live.S.ancestor_order(forms, i)]


class Form:
    def __init__(self, ls, i, scope=None):
        self.line = i
        self.kind = ls[i].split()[0][1:]
        self.scope = scope_of(ls, i) if scope is None else scope
        self.text = portsort(self.scope, ls[i]) if self.kind in live.KIND_TOK else ls[i]  # the written atom order, with ports in column order
        self.written = self.written_key = self.partial = self.prefix = None  # the written order's walk, kept apart from the order sum
        self.bits_by = {}  # token key of an order from every() or sampled -> bits, or None for an order past DELTA
        self.tried = self.refused = self.none = self.dropped = 0
        self.status = 'no draw' if self.kind not in live.KIND_TOK else None
        self.sizes, self.n_orders, self.error, self.o = [], None, None, None

    def plan(self):
        """The form's orders: sizes and the count by the guard rule. A form that does not read back keeps its written figure and has `error`."""
        if self.status is not None:
            return
        try:
            self.o = Orders(self.text)
        except Exception as e:  # noqa: BLE001
            self.error = '%s: %s' % (type(e).__name__, str(e)[:200])
            counts['forms that do not read back'] += 1
            return
        self.sizes, self.n_orders = [b.n for b in self.o.bodies], self.o.total

    def walk(self, text, limit):
        """Walks text once: a tuple of the bits and the key, or None where it adds nothing."""
        self.tried += 1
        try:
            got, key = F.walked(self.scope, text, self.kind, limit)
        except Exception:  # noqa: BLE001
            self.refused += 1
            return None
        if key in self.bits_by:
            return None
        if got is OVER:
            self.dropped += 1
            self.bits_by[key] = None
            return None
        if got is None:
            self.none += 1
            return None
        self.bits_by[key] = got
        return got, key

    def limit(self):
        b = [x for x in self.bits_by.values() if x is not None]
        return min(b) + DELTA if b else None

    def first(self):
        """The written order's walk. It sets `written` and nothing else."""
        try:
            got, key = F.walked(self.scope, self.text, self.kind, None)
        except Exception:  # noqa: BLE001
            counts['written orders the reader refuses'] += 1
            return
        if got is None:
            self.partial = round(sum(F.last_parts.values()), 2)
        else:
            self.written, self.written_key = got, key

    def orders(self):
        o = self.o
        if o.total == 1:
            if self.written is not None:
                self.bits_by[self.written_key] = self.written
                self.status = 'one'
            else:
                self.status = 'none'
            return
        if o.total is not None and o.total <= CAP:
            for x in o.every():
                self.walk(o.render(x), self.limit())
            self.status = 'exact'
        else:
            self.sampled(o, rng_of(o))
            self.status = 'bound'
        if not any(x is not None for x in self.bits_by.values()) and self.written is None:
            self.status = 'none'

    def sampled(self, o, rng):
        """The orders of a form past CAP: random orders, then swaps from the cheapest. A heap holds the orders with bits, so that a swap starts from the cheapest not yet expanded. The written order is not in the heap."""
        seen, heap, walked, draws = set(), [], 0, 0
        target = max(1, int(CAP * SAMPLE_SHARE))

        def go(x):
            nonlocal walked
            seen.add(x)
            r0 = self.refused
            got = self.walk(o.render(x), self.limit())
            if self.refused == r0:
                walked += 1
            if got:
                heapq.heappush(heap, (got[0], x))
        while walked < target and draws < DRAWS * CAP:
            draws += 1
            x = o.sample(rng)
            if x not in seen:
                go(x)
        while walked < CAP and heap:
            _, x = heapq.heappop(heap)
            for y in o.neighbours(x):
                if walked >= CAP:
                    break
                if y not in seen:
                    go(y)

    def row(self):
        vals = {k: v for k, v in self.bits_by.items() if v is not None}
        tight = dict(vals)
        if self.written is not None:
            tight.setdefault(self.written_key, self.written)
        bits = round(lse2(list(vals.values())), 3) if vals else None
        if bits is None and self.status == 'written':
            bits = self.written  # the figure that a form has where no order past the written one has been walked
        r = dict(line=self.line, kind=self.kind, nscope=len(self.scope), sizes=self.sizes, orders=self.n_orders, tried=self.tried, refused=self.refused, valid=len(vals), dropped=self.dropped, none=self.none, status=self.status,
                 bits=bits, best=min(vals.values()) if vals else self.written, written=self.written, tight=round(lse2(list(tight.values())), 3) if tight else None, prefix=self.prefix, partial=self.partial)
        if self.error:
            r['error'] = self.error
        return r


def form_lines(ls):
    return [i for i, x in enumerate(ls) if not x.startswith('(OUT')]


def report(row, fs, done):
    forms = [f.row() for f in fs]
    with_bits = [f['bits'] for f in forms if f['bits'] is not None]
    row.update(forms=forms, worst=max(with_bits, default=None), sum=round(sum(with_bits), 3), seconds=round(time.time() - t0, 1), cpu=round(time.process_time() + F.OS.cpu, 1), times={k: round(v, 2) for k, v in times.items()}, counts=dict(counts), finished=done)
    print(json.dumps(row), flush=True)


def main():
    row = dict(task=task, base_sha=hashlib.sha256('\n'.join(base_lines).encode()).hexdigest()[:16], cap=CAP, delta=DELTA)
    ls = list(base_lines)
    with timed('canonical'):
        canon, row['canon_kept'] = canonical(ls)
    fs = [Form(ls, i, scope_of(canon, i)) for i in form_lines(ls)]
    draw = [f for f in fs if f.status is None]
    for f in draw:
        f.plan()
    for f in draw:
        f.first()
        got = F.read_form(ls, f.line)
        f.prefix = got if isinstance(got, (int, float)) else None
        if f.written is not None:
            f.status = 'written'
    report(row, fs, False)
    last = time.time()
    for f in sorted(draw, key=lambda f: -(f.written if f.written is not None else 1e9)):
        if f.error:
            continue
        if time.time() - t0 > SECONDS:
            row['late'] = True
            break
        try:
            f.orders()
        except Exception as e:  # noqa: BLE001
            f.error = '%s: %s' % (type(e).__name__, str(e)[:200])
            if f.status is None:
                f.status = 'written' if f.written is not None else 'none'
        if time.time() - last > EVERY:
            report(row, fs, False)
            last = time.time()
    for f in draw:
        if f.status is None:
            f.status = 'none'
    report(row, fs, True)


if __name__ == '__main__':
    load_sampler()
    setup(*sys.argv[1:4])
    main()
