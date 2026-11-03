"""Task-independent forms in gold, as design.md gives them.

  /Users/davidlu/code/arc-workspace/.venv/bin/python ti_forms.py [SECONDS]

Writes train-shapes.jsonl (one line per training stem), then rows.jsonl (one line per form of
the 59 tasks, streamed per task), then table.md. It skips the stems and tasks it has, and
stops after SECONDS (default 20) of work. Run it again until it prints "done".

Column types come from engine/lib/registry.sexpr (lib relations, macros, facts, components)
and from the program text. No Souffle or Arclog run is needed.
"""
import collections, hashlib, json, os, re, statistics, sys, time

T0 = time.time()
LIMIT = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
ROOT = '/Users/davidlu/code/arc-workspace/'
DS = ROOT + 'work/lm/data-study/'
HERE = DS + 'gold/gold-ti-forms/'
FLAT = ROOT + 'work/lm/data-study/gold/gold-export/flat/'
REG = ROOT + 'engine/lib/registry.sexpr'
BITS = DS + 'gold/gold-v3-dag-bits/reread-kit/merged.jsonl'
TASKS = DS + 'gold/gold-heldout-ramp-dag/heldout-ramp.jsonl'
EVAL99 = DS + 'features-worker/arm/eval-tasks.txt'
MANIFEST = ROOT + 'work/lm/data-study/gold/gold-export/manifest.json'
TRAIN_OUT = HERE + 'train-shapes.jsonl'
ROWS_OUT = HERE + 'rows.jsonl'
TABLE_OUT = HERE + 'table.md'
RECUR = 3

sys.path.insert(0, DS + 'sampler/sampler-worker/sampler-ident-match-read')
import common as C  # noqa: E402  (gold_forms)

# Kinds that choose a value for the task. The design names DET; RIGID_DET and CHOOSE are the
# other determination and choice forms. See the report for this reading.
NON_TI_KINDS = {'DET', 'RIGID_DET', 'CHOOSE'}

TOK = re.compile(r'[()]|[^\s()]+')


def parse_all(text):
    stack, top = [], []
    cur = top
    for t in TOK.findall(text):
        if t == '(':
            n = []
            cur.append(n)
            stack.append(cur)
            cur = n
        elif t == ')':
            cur = stack.pop()
        else:
            cur.append(t)
    return top


def render(x):
    return x if isinstance(x, str) else '(' + ' '.join(render(y) for y in x) + ')'


# ---------------------------------------------------------------- the lib registry

def fix_type(t):
    if isinstance(t, list):
        return 'D4' if t and t[0] == 'pose-or' else 'Pose'
    return 'Pose' if t == 'shared-pose' else t


def parse_rules(items):
    rules = []
    for it in items:
        if isinstance(it, list) and it and it[0] == 'types':
            for w in it[1:]:
                if isinstance(w, list) and w and w[0] == 'when':
                    conds = [(c[0], c[1]) for c in w[1] if isinstance(c, list) and len(c) == 2 and c[0] != 'same-frame']
                    if any(isinstance(c, list) and c and c[0] == 'same-frame' for c in w[1]):
                        continue
                    rules.append((conds, (w[2][0], w[2][1])))
    return rules


def mkspec(cols, rules=()):
    """cols: (name, type, group, field). A group column is a record, such as a key."""
    s = dict(cols=cols, rules=list(rules), plain={}, groups={})
    for n, t, g, f in cols:
        if g is None:
            s['plain'][n] = t
        else:
            s['groups'].setdefault(g, {})[f] = t
    return s


class Registry:
    def __init__(self):
        text = '\n'.join(re.sub(r';.*$', '', l) for l in open(REG))
        self.rel, self.comp, self.prop = {}, {}, {}
        for f in parse_all(text):
            k = f[0]
            if k == 'relation':
                cols = [(c[0], fix_type(c[1]), None, None) for c in f[2][1:]]
                self.rel[f[1]] = mkspec(cols, parse_rules(f[3:]))
            elif k == 'fact':
                cols = [(c[0], fix_type(c[1]), None, None) for c in f[2][1:]]
                self.rel[f[1]] = mkspec(cols)
            elif k == 'macro':
                cols = [(c[0], fix_type(c[2]), None, None) for c in f[2][1:]]
                sp = mkspec(cols, parse_rules(f[3:]))
                sp['mcols'] = [(c[0], c[1]) for c in f[2][1:]]
                sp['body'] = [a for a in f[3:] if isinstance(a, list) and a and a[0] not in ('modes', 'frames', 'types')]
                self.rel[f[1]] = sp
            elif k == 'component':
                self.comp[f[1]] = self.parse_comp(f)
            elif k == 'proposer':
                cs = [c for c in f if isinstance(c, list) and c and c[0] == 'columns'][0][1:]
                self.prop[f[1]] = [(c[0], fix_type(c[1])) if isinstance(c, list) else (c, {'C': 'Color', 'N': 'Nat', 'A': 'Axis'}.get(c[0], '?')) for c in cs]

    @staticmethod
    def parse_comp(f):
        params = {}
        for p in f[3][1:]:
            if isinstance(p, list):
                params[p[0]] = p[1]
            else:
                params[p] = None
        d = dict(params=params, inputs={}, outputs=[])
        for sec in f[4:]:
            for e in sec[1:]:
                cols = [(c[0], c[1]) for c in e[1:] if isinstance(c, list) and len(c) == 2 and isinstance(c[1], str) and c[0] not in ('copies', 'frames', 'default')]
                if sec[0] == 'inputs':
                    d['inputs'][e[0]] = dict(cols)
                else:
                    d['outputs'].append((e[0], cols))
        return d


# ---------------------------------------------------------------- labels and types

def lab(tok):
    """(name, mark) of a label token, or (None, None) for a literal."""
    if not isinstance(tok, str):
        return None, None
    mark = tok[0] if tok[0] in '*^' else ''
    name = tok.lstrip('*^')
    if re.fullmatch(r'-?\d+', name) or name == '_':
        return None, None
    return name, mark


UNDER = {('Box', 'Position'), ('Box', 'Offset'), ('Int', 'Nat'), ('D4', 'C4'), ('Dir8', 'Dir'), ('Dir8', 'DiagDir'), ('Axis4', 'Axis'), ('Axis4', 'DiagAxis')}


def merge(old, new):
    """A label that two sites type differently takes the type that is under the other (Position, Offset under Box; Nat under Int; C4 under D4; Dir, DiagDir under Dir8; Axis, DiagAxis under Axis4)."""
    if old is None or old == '?':
        return new
    if new is None or new == '?' or old == new:
        return old
    if (old, new) in UNDER:
        return new
    return old


COMPARE = {'=', '!=', '<', '<=', '>', '>='}
STRUCT = {'NOT', 'OR', 'ALL', 'IF', 'AND'}
MARKS = {'ONE'}


def flat_atoms(body, out):
    """Every relation atom of a body, however deeply nested, in order."""
    for a in body:
        if not isinstance(a, list) or not a:
            continue
        if isinstance(a[0], list):
            flat_atoms(a, out)
        elif a[0] in STRUCT:
            flat_atoms(a[1:], out)
        elif a[0] not in MARKS:
            out.append(a)
    return out


class Typer:
    def __init__(self, reg, heads, unk):
        self.reg, self.heads, self.unk = reg, heads, unk

    def spec(self, rel):
        if rel in self.reg.rel:
            return self.reg.rel[rel]
        if rel.startswith('&'):
            return self.heads.get(rel)
        return None

    def sites(self, sp, atom):
        """(label token, column key, declared type) for each site of an atom."""
        out = []
        for site in atom[1:]:
            if isinstance(site, str):
                cn, args = lab(site)[0], [site]
                if cn is None:
                    continue
            elif site and isinstance(site[0], str) and site[0].startswith(':'):
                cn, args = site[0][1:], site[1:]
            else:
                continue
            if cn in sp['groups']:
                flds = sp['groups'][cn]
                for a in args:
                    if isinstance(a, str):
                        f, l = lab(a)[0], a
                    elif a and isinstance(a[0], str) and a[0].startswith(':') and len(a) > 1:
                        f, l = a[0][1:], a[1]
                    else:
                        continue
                    if f not in flds and len(flds) == 1:
                        f = next(iter(flds))
                    out.append((l, (cn, f), flds.get(f, '?')))
            elif cn in sp['plain']:
                if args and isinstance(args[0], str):
                    out.append((args[0], (cn, None), sp['plain'][cn]))
            elif args and isinstance(args[0], str):
                # a lifted read of a derived relation names the Example column E
                out.append((args[0], (cn, None) if cn == 'E' and atom[0].startswith('&') else None, 'Example' if cn == 'E' and atom[0].startswith('&') else '?'))
        return out

    def infer(self, body, env, made):
        atoms = flat_atoms(body, [])
        for _ in range(4):
            changed = False
            for a in atoms:
                rel = a[0]
                if rel in COMPARE:
                    if len(a) >= 3:
                        n1, m1 = lab(a[1])
                        n2, _ = lab(a[2])
                        if rel == '=' and n1 and m1 == '*':
                            t = env.get(n2) if n2 else 'Int'
                            if t and env.get(n1) != t and not made.get(n1):
                                env[n1], made[n1] = t, True
                                changed = True
                        elif rel in ('=', '!=') and n1 and n2 and env.get(n1) and env.get(n2):
                            # a comparison of two labels puts both at the narrower type
                            for x, y in ((n1, n2), (n2, n1)):
                                t = merge(env[x], env[y])
                                if t != env[x]:
                                    env[x] = t
                                    changed = True
                    continue
                sp = self.spec(rel)
                if sp is None:
                    if not rel.startswith('&'):
                        self.unk[rel] += 1
                    continue
                items = self.sites(sp, a)
                lt = {}
                for l, ck, dt in items:
                    n, _ = lab(l)
                    if n and ck and ck[1] is None:
                        lt[ck[0]] = env.get(n)
                refined = {}
                if 'body' in sp:
                    menv, mmade = {}, {}
                    declared = {c: t for c, t, _, _ in sp['cols']}
                    lab_of = dict(sp['mcols'])
                    for l, ck, dt in items:
                        n, _ = lab(l)
                        if ck and ck[1] is None and ck[0] in lab_of and lab_of[ck[0]] not in menv:
                            menv[lab_of[ck[0]]] = (env.get(n) if n else None) or declared[ck[0]]
                            mmade[lab_of[ck[0]]] = True
                    self.infer(sp['body'], menv, mmade)
                    for c, ln in sp['mcols']:
                        if menv.get(ln) and menv[ln] != '?':
                            refined[c] = menv[ln]
                for conds, (rc, rt) in sp['rules']:
                    if all(lt.get(c) == t for c, t in conds):
                        refined[rc] = rt
                for l, ck, dt in items:
                    n, mark = lab(l)
                    if n is None:
                        continue
                    t = refined.get(ck[0], dt) if ck and ck[1] is None else dt
                    if t == 'Pose':
                        t = next((v for k, v in lt.items() if v and v != env.get(n)), '?')
                    old = env.get(n)
                    if mark and not made.get(n):
                        env[n], made[n] = t, True
                    elif old is None:
                        env[n] = t
                    else:
                        env[n] = merge(old, t)
                    changed |= env.get(n) != old
            if not changed:
                break


def stars(body, names_after=None):
    """Labels that a body makes and exports, in order of first appearance."""
    out = []
    for a in body:
        if not isinstance(a, list) or not a:
            continue
        if isinstance(a[0], list):
            out += stars(a)
        elif a[0] in ('NOT', 'ALL'):
            continue
        elif a[0] == 'OR':
            br = a[1:]
            later = [names(b) for b in br[1:]]
            for n in stars(br[0]):
                if all(n in s for s in later):
                    out.append(n)
        elif a[0] == 'IF':
            if len(a) >= 4:
                nm = names(a[3])
                out += [n for n in stars(a[2]) if n in nm]
        elif a[0] in COMPARE:
            if len(a) >= 3:
                n1, m1 = lab(a[1])
                if n1 and m1 == '*':
                    out.append(n1)
        else:
            for site in a[1:]:
                for tok in leaves(site):
                    n, m = lab(tok)
                    if n and m == '*':
                        out.append(n)
    return list(dict.fromkeys(out))


def names(x):
    s = set()
    for tok in leaves(x):
        n, _ = lab(tok)
        if n:
            s.add(n)
    return s


def leaves(x):
    if isinstance(x, str):
        if not x.startswith(':'):
            yield x
        return
    for y in x:
        yield from leaves(y)


def expand(cn, ct, comp, bind, key_cols):
    """The columns that one column of a component relation makes."""
    if ct == 'Key' and cn == 'key':
        return [('key', t, 'key', n) for n, t in key_cols]
    if ct in comp['params']:
        v = bind.get(ct)
        if v is None:
            return []
        if isinstance(v, str):
            return [(cn, v, None, None)]
        return [(cn, t, cn, n) for n, t in v]
    return [(cn, ct, None, None)]


def type_form(reg, heads, x, unk):
    """Head columns of a RULE or INIT form. Returns (head types by output, key types, relations read)."""
    ty = Typer(reg, heads, unk)
    label = x[1]
    kind = x[0]
    if kind == 'RULE':
        body = x[2:]
        if len(body) == 1 and isinstance(body[0], str) and body[0] in reg.prop:
            cols = [(n, t, None, None) for n, t in reg.prop[body[0]]]
            heads[label] = mkspec(cols)
            return dict(head=[c[1] for c in cols]), None
        env, made = {}, {}
        ty.infer(body, env, made)
        cols = [(n, env.get(n, '?'), None, None) for n in stars(body)]
        heads[label] = mkspec(cols)
        return dict(head=[c[1] for c in cols]), None
    comp = reg.comp.get(x[2])
    if comp is None:
        unk['component ' + x[2]] += 1
        return dict(head=['?']), ['?']
    keyenv, keymade, key_cols = {}, {}, []
    inputs = []
    for part in x[3:]:
        if part and part[0] == 'key':
            ty.infer(part[1], keyenv, keymade)
            seen = []
            for a in flat_atoms(part[1], []):
                for site in a[1:]:
                    for tok in leaves(site):
                        n, m = lab(tok)
                        if n and m == '^' and n not in seen:
                            seen.append(n)
            key_cols = [(n, keyenv.get(n, '?')) for n in seen]
            inputs += [(p, True) for p in part[2:]]
        else:
            inputs.append((part, False))
    bind = {}
    for inp, keyed in inputs:
        name = inp[0]
        ci = comp['inputs'].get(name)
        env, made = dict(keyenv), dict(keymade)
        ty.infer(inp[2:], env, made)
        if ci is None:
            continue
        for site in inp[1]:
            if isinstance(site, str):
                cn, args = lab(site)[0], [site]
            else:
                cn, args = site[0][1:], site[1:]
            ct = ci.get(cn)
            if ct in comp['params'] and (ct != 'Key' or cn != 'key'):
                if len(args) == 1 and isinstance(args[0], str):
                    n, _ = lab(args[0])
                    t = env.get(n, '?') if n else '?'
                else:
                    t = []
                    for a in args:
                        if isinstance(a, str):
                            t.append((lab(a)[0], env.get(lab(a)[0], '?')))
                        else:
                            n = lab(a[1])[0] if len(a) > 1 else None
                            t.append((a[0][1:], env.get(n, '?') if n else '?'))
                old = bind.get(ct)
                if old is None:
                    bind[ct] = t
                elif isinstance(old, str) and isinstance(t, str) and old != t:
                    bind[ct] = 'Box' if {old, t} <= {'Box', 'Position', 'Offset'} else old
    for p, dflt in comp['params'].items():
        if p not in bind and p != 'Key' and dflt:
            bind[p] = dflt
    outs, allcols = {}, []
    for oname, ocols in comp['outputs']:
        cols = []
        for cn, ct in ocols:
            cols += expand(cn, ct, comp, bind, key_cols)
        heads['%s.%s' % (label, oname)] = mkspec(cols)
        outs[oname] = [c[1] for c in cols]
        allcols += cols
    for iname, icols in comp['inputs'].items():
        if iname in outs:
            continue
        cols = []
        for cn, ct in icols.items():
            cols += expand(cn, ct, comp, bind, key_cols)
        heads['%s.%s' % (label, iname)] = mkspec(cols)
    return dict(head=outs), [t for _, t in key_cols]


# ---------------------------------------------------------------- canonical text

def blind(s):
    return re.sub(r'&r\d+', '&_', s)


def canon_atom(a):
    if not isinstance(a, list) or not a or isinstance(a[0], list):
        return a
    h = a[0]
    if h == 'NOT':
        return ['NOT'] + [canon_atom(y) for y in a[1:]]
    if h == 'OR':
        return ['OR'] + [canon_body(b) for b in a[1:]]
    if h in ('ALL', 'IF'):
        return [h] + [canon_body(b) for b in a[1:]]
    return a


def canon_body(body):
    if not isinstance(body, list):
        return body
    items = [canon_atom(a) for a in body]
    return sorted(items, key=lambda a: (blind(render(a)), render(a)))


def canon_form(x):
    k = x[0]
    if k == 'RULE':
        return x[:2] + canon_body(x[2:])
    if k == 'INIT':
        parts = []
        for p in x[3:]:
            if p and p[0] == 'key':
                parts.append(['key', canon_body(p[1])] + [canon_input(i) for i in p[2:]])
            else:
                parts.append(canon_input(p))
        return x[:3] + parts
    return x


def canon_input(i):
    return i[:2] + canon_body(i[2:])


def rename(text):
    m = {}

    def f(mo):
        return m.setdefault(mo.group(0), '&r%d' % len(m))
    return re.sub(r'&r\d+', f, text)


# ---------------------------------------------------------------- one program

def analyze(text, reg):
    lines, reads, depth = C.gold_forms(text)
    trees = [parse_all(l)[0] for l in lines]
    kinds = [t[0] for t in trees]
    comp_of = {t[1]: t[2] for t in trees if t[0] == 'INIT'}
    ti = []
    for i, r in enumerate(reads):
        ti.append(kinds[i] not in NON_TI_KINDS and all(ti[q] for q in r))
    heads, unk = {}, collections.Counter()
    ctrees = [canon_form(t) for t in trees]
    ctext = [render(t) for t in ctrees]
    anc_cache = {}

    def anc(i):
        if i not in anc_cache:
            s = {i}
            for r in reads[i]:
                s |= anc(r)
            anc_cache[i] = s
        return anc_cache[i]
    out = []
    for i, t in enumerate(trees):
        row = dict(line=i, kind=kinds[i], depth=depth[i], reads=reads[i], ti=ti[i], root=ti[i] and not reads[i], literal=False, one=False, empty=False, shape=None, exact=None, typed=None)
        if ti[i]:
            hd, keyt = type_form(reg, heads, ctrees[i], unk)
            body = t[2:] if kinds[i] == 'RULE' else t[3:]
            row['literal'] = any(re.fullmatch(r'-?\d+', y) for y in leaves(body))
            row['one'] = any(isinstance(a, list) and a and a[0] == 'ONE' for a in body)
            if kinds[i] == 'RULE':
                rels = {y for y in body if isinstance(y, str)}
                for a in flat_atoms(t[2:], []):
                    r = a[0]
                    if r.startswith('&'):
                        mo = re.match(r'(&r\d+)(?:\.(\w+))?$', r)
                        r = '%s.%s' % (comp_of.get(mo.group(1), '?'), mo.group(2)) if mo and mo.group(2) else '&RULE'
                    rels.add(r)
                types = hd['head']
                shape = 'RULE|%s|%s|ident=%d' % (','.join(sorted(rels)), ','.join(types), 'Ident' in types)
                bad = '?' in types
                row['empty'] = not types
            else:
                outs = hd['head']
                alltypes = [y for v in outs.values() for y in v]
                shape = 'INIT|%s|%s|ident=%d|key=%s' % (t[2], ';'.join('%s(%s)' % (o, ','.join(v)) for o, v in outs.items()), 'Ident' in alltypes, ','.join(keyt) if keyt else 'none')
                bad = '?' in alltypes or '?' in (keyt or [])
            row['shape'] = shape
            row['typed'] = not bad
            a = sorted(anc(i))
            ex = rename('\n'.join(ctext[j] for j in a))
            row['exact'] = hashlib.sha256(ex.encode()).hexdigest()[:16]
        out.append(row)
    return out, unk


# ---------------------------------------------------------------- driver

def md(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join(['---'] * len(head)) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out) + '\n'


def med(v):
    return '%.3g' % statistics.median(v) if v else '-'


BINS = [('0', lambda x: x == 0), ('(0,.25]', lambda x: 0 < x <= .25), ('(.25,.5]', lambda x: .25 < x <= .5), ('(.5,.75]', lambda x: .5 < x <= .75), ('(.75,1]', lambda x: x > .75)]


EVAL_TABLES = DS + 'sampler/sampler-worker/sampler-shape-read/sampler-gold-tables-final.jsonl'


def check_types(reg):
    """Compare the static head types with the evaluated tables of the 37 and the 13 (sampler-gold-tables-final.jsonl), as a multiset of types per form."""
    c = collections.Counter()
    if not os.path.exists(EVAL_TABLES):
        return None
    for r in read_jsonl(EVAL_TABLES):
        text = open(FLAT + r['task'] + '.arclog').read()
        lines = [x for x in text.strip().split('\n') if not x.startswith('(OUT')]
        if [f['text'] for f in r['forms']] != lines:
            c['tasks with other gold text'] += 1
            continue
        c['tasks compared'] += 1
        rows, _ = analyze(text, Registry())
        tabs = collections.defaultdict(list)
        for tb in r['tables']:
            tabs[tb['form']].append(tb)
        for x in rows:
            tb = tabs.get(x['line'])
            if not x['ti'] or not tb or any('types' not in q for q in tb):
                continue
            mine = x['shape'].split('|')
            if x['kind'] == 'RULE':
                ok = sorted(mine[2].split(',') if mine[2] else []) == sorted(tb[0]['types'])
            else:
                pool = [sorted(q['types']) for q in tb]
                ok = True
                for o in mine[2].split(';'):
                    v = sorted(o.split('(')[1].rstrip(')').split(',')) if o.split('(')[1].rstrip(')') else []
                    if not v:
                        continue
                    if v in pool:
                        pool.remove(v)
                    else:
                        ok = False
            c['forms agree' if ok else 'forms differ'] += 1
    return c


def build(tr, rows, tasks, bits, an, man):
    by = collections.defaultdict(list)
    for r in rows:
        by[r['task']].append(r)
    sets = {'37': [t['task'] for t in tasks if t['source'] == 'eval-37'], 'ramp': [t['task'] for t in tasks if t['source'] != 'eval-37']}
    classes = [('root TI', lambda r: r['root_ti']), ('all TI', lambda r: r['ti'])]
    out = ['# Task-independent forms in gold\n', 'Figures of `design.md`. `rows.jsonl` holds one line per form; `train-shapes.jsonl` holds the training stems. A shape or an exact text recurs when it is in %d or more of the %d training stems; for a task that is a training stem, its own stem is left out of the count.\n' % (RECUR, len(tr))]
    s_ok = {}
    for t in tasks:
        s_ok[t['task']] = by[t['task']][0]['base_ok']
    # figures
    out.append('## Counts and depth\n')
    hd = ['set', 'class', 'programs', 'forms', 'class forms', 'median share of forms', 'median share of depth', 'share of depth in bins ' + ' / '.join(b for b, _ in BINS)]
    rr = []
    for sn, ts in sets.items():
        for cn, cf in classes:
            nf = [len(by[t]) for t in ts]
            cnt = [sum(1 for r in by[t] if cf(r)) for t in ts]
            pd = [max(r['depth'] for r in by[t]) for t in ts]
            cd = [max([r['depth'] for r in by[t] if cf(r)], default=0) for t in ts]
            sh = [c / n for c, n in zip(cnt, nf)]
            dsh = [c / p for c, p in zip(cd, pd)]
            rr.append([sn, cn, len(ts), sum(nf), sum(cnt), med(sh), med(dsh), ' / '.join(str(sum(1 for x in dsh if f(x))) for _, f in BINS)])
    out.append(md(hd, rr))
    out.append('A program with no form of the class counts as share 0.\n')
    out.append('## Bits\n')
    hd = ['set', 'class', 'programs with bits', 'class forms with bits', 'median bits', 'sum, class', 'sum, all forms', 'class share of sum']
    rr = []
    for sn, ts in sets.items():
        ok = [t for t in ts if s_ok[t]]
        allsum = sum(r['bits'] or 0 for t in ok for r in by[t])
        for cn, cf in classes:
            v = [r['bits'] for t in ok for r in by[t] if cf(r) and r['bits'] is not None]
            rr.append([sn, cn, '%d of %d' % (len(ok), len(ts)), len(v), med(v), '%.1f' % sum(v), '%.1f' % allsum, '%.3f' % (sum(v) / allsum if allsum else 0)])
    out.append(md(hd, rr))
    out.append('### Bits of recurring forms\n')
    out.append('A TI form counts when its identity recurs and the identity of each TI form it reads, transitively, recurs too. Share is of the set\'s bits over all forms.\n')
    hd = ['set', 'identity', 'forms', 'forms with bits', 'sum of bits', 'sum, all forms', 'share of sum']
    rr = []
    for sn, ts in sets.items():
        ok = [t for t in ts if s_ok[t]]
        allsum = sum(r['bits'] or 0 for t in ok for r in by[t])
        for key, tk in (('shape', 'train_shape'), ('exact', 'train_exact')):
            n = nb_ = 0
            tot = 0.0
            for t in ts:
                closed = {}
                for r in by[t]:
                    closed[r['line']] = bool(r['ti'] and r[tk] >= RECUR and all(closed.get(q) for q in r['reads']))
                    if closed[r['line']]:
                        n += 1
                        if r['bits'] is not None:
                            nb_ += 1
                            tot += r['bits']
            rr.append([sn, key, n, nb_, '%.1f' % tot, '%.1f' % allsum, '%.3f' % (tot / allsum if allsum else 0)])
    out.append(md(hd, rr))
    out.append('## Recurrence\n')
    hd = ['set', 'class', 'distinct shapes', 'recurring shapes', 'distinct exact texts', 'recurring exact texts']
    rr = []
    for sn, ts in sets.items():
        for cn, cf in classes:
            fs = [r for t in ts for r in by[t] if cf(r)]
            sh = {r['shape']: r['train_shape'] for r in fs}
            ex = {r['exact']: r['train_exact'] for r in fs}
            rr.append([sn, cn, len(sh), sum(1 for v in sh.values() if v >= RECUR), len(ex), sum(1 for v in ex.values() if v >= RECUR)])
    out.append(md(hd, rr))
    # lists
    for key, tk, name in (('shape', 'train_shape', 'shapes'), ('exact', 'train_exact', 'exact texts')):
        g = {}
        for r in rows:
            if r['ti'] and r[tk] >= RECUR:
                d = g.setdefault(r[key], dict(train=r[tk], tasks=set(), t37=set(), ramp=set(), root=False, sample='%s:%d' % (r['task'], r['line']), shape=r['shape']))
                d['tasks'].add(r['task'])
                d['train'] = max(d['train'], r[tk])
                d['t37' if r['set'] == '37' else 'ramp'].add(r['task'])
                d['root'] |= r['root_ti']
        lst = sorted(g.items(), key=lambda kv: (-len(kv[1]['tasks']), -kv[1]['train'], kv[0]))
        out.append('### Recurring %s: %d, by tasks among the 59 (top 30)\n' % (name, len(lst)))
        if key == 'shape':
            out.append(md(['shape', 'root', 'training stems', 'tasks of 59', 'tasks of 37', 'tasks of ramp'], [[k, int(d['root']), d['train'], len(d['tasks']), len(d['t37']), len(d['ramp'])] for k, d in lst[:30]]))
        else:
            out.append(md(['exact', 'root', 'sample', 'shape', 'training stems', 'tasks of 59', 'tasks of 37', 'tasks of ramp'], [[k, int(d['root']), d['sample'], d['shape'], d['train'], len(d['tasks']), len(d['t37']), len(d['ramp'])] for k, d in lst[:30]]))
    out.append('## Start depth\n')
    out.append('The greatest depth of a TI form whose identity recurs, per program; 0 when none does. Training counts leave a task\'s own stem out. Share of depth is the start depth over the program\'s depth.\n')
    hd = ['set', 'identity', 'programs', 'start depth 0', '1', '2', '3 or more', 'median', 'median share of depth', 'programs at .25 or more']
    rr = []
    for sn, ts in sets.items():
        for key, tk in (('shape', 'train_shape'), ('exact', 'train_exact')):
            sd = [max([r['depth'] for r in by[t] if r['ti'] and r[tk] >= RECUR], default=0) for t in ts]
            pdp = [max(r['depth'] for r in by[t]) for t in ts]
            shr = [a / b for a, b in zip(sd, pdp)]
            rr.append([sn, key, len(ts), sum(x == 0 for x in sd), sum(x == 1 for x in sd), sum(x == 2 for x in sd), sum(x >= 3 for x in sd), med(sd), med(shr), sum(x >= .25 for x in shr)])
    out.append(md(hd, rr))
    # checks
    out.append('## Checks\n')
    n_ok = sum(1 for t in tasks if s_ok[t['task']])
    out.append('- `base_sha` equals the sha256 of `"\\n".join(text.splitlines())`, first 16 hex digits, on %d of %d tasks%s.' % (n_ok, len(tasks), '' if n_ok == len(tasks) else '; the others: ' + ' '.join(t['task'] for t in tasks if not s_ok[t['task']])))
    nb = collections.Counter()
    for r in rows:
        if r['base_ok'] and r['bits'] is None:
            nb[(r['kind'], 'TI' if r['ti'] else 'not TI')] += 1
    out.append('- Forms with no bits, on tasks whose `base_sha` matches: %d (%s). Forms on tasks whose `base_sha` does not match: %d.' % (sum(nb.values()), ', '.join('%s %s %d' % (k[0], k[1], v) for k, v in sorted(nb.items())) or 'none', sum(1 for r in rows if not r['base_ok'])))
    kmis = sum(1 for r in rows if r['base_ok'] and r['bits_kind'] != r['kind'])
    out.append('- Forms whose kind in `merged.jsonl` differs from the gold text: %d.' % kmis)
    u59 = sorted({r['task'] for r in rows if r['ti'] and not r['typed']})
    utr = [r['stem'] for r in tr if r['untyped']]
    out.append('- Stems with a TI form whose shape has a column of unresolved type: %d of %d training stems, %d of the 59 tasks%s.' % (len(utr), len(tr), len(u59), (' (' + ' '.join(u59) + ')') if u59 else ''))
    unk = collections.Counter(u for r in tr for u in r['unk'])
    unk59 = collections.Counter(u for _, (_, (_, k)) in an.items() for u in k)
    out.append('- Relations or components in TI forms that the registry does not hold: training stems %s; the 59 tasks %s.' % (dict(unk) or 'none', dict(unk59) or 'none'))
    cc = check_types(Registry())
    if cc is not None:
        out.append('- Static head types against the evaluated tables of `sampler-gold-tables-final.jsonl` (multiset of column types per TI form with a finished table): %s.' % dict(cc))
    one59 = [r for r in rows if r['ti'] and r['one']]
    out.append('- TI forms with a `ONE` mark (a pick of one row; kept TI because their kind is RULE): training stems %d forms in %d stems; the 59 tasks %d forms (%s).' % (sum(r['one'] for r in tr), sum(1 for r in tr if r['one']), len(one59), ', '.join('%s:%d' % (r['task'], r['line']) for r in one59) or 'none'))
    out.append('- TI forms whose head has no column (a fact, or every site projected away): training stems %d; the 59 tasks %d.' % (sum(r['empty'] for r in tr), sum(1 for r in rows if r['ti'] and r['empty'])))
    lit = [r for r in rows if r['root_ti'] and r['literal']]
    out.append('- Root TI forms of the 59 with an integer literal: %d (%s).' % (len(lit), ', '.join('%s:%d' % (r['task'], r['line']) for r in lit)))
    nonti = collections.Counter(r['kind'] for r in rows if r['kind'] in NON_TI_KINDS)
    out.append('- Forms of the 59 that are not TI by kind: %s.' % dict(nonti))
    apx = [r['stem'] for r in tr if r['approximated']]
    out.append('- Approximated stems among the training stems: %d (%s). Approximated stems among the 59: %s.' % (len(apx), ' '.join(apx), ' '.join(t['task'] for t in tasks if 'approximated' in man[t['task']]) or 'none'))
    out.append('- Tasks of the 59 that are also training stems (the ramp): %d.' % sum(1 for t in tasks if t['task'] in {r['stem'] for r in tr}))
    open(TABLE_OUT, 'w').write('\n'.join(out) + '\n')



def read_jsonl(p):
    out = []
    if os.path.exists(p):
        for l in open(p):
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    return out


def main():
    reg = Registry()
    h99 = set(open(EVAL99).read().split())
    man = json.load(open(MANIFEST))['stems']
    stems = sorted(f[:-7] for f in os.listdir(FLAT) if f.endswith('.arclog'))
    train = [s for s in stems if s not in h99]
    have = {r['stem'] for r in read_jsonl(TRAIN_OUT)}
    todo = [s for s in train if s not in have]
    n = 0
    with open(TRAIN_OUT, 'a') as f:
        for s in todo:
            if time.time() - T0 > LIMIT:
                break
            rows, unk = analyze(open(FLAT + s + '.arclog').read(), reg)
            ti = [r for r in rows if r['ti']]
            rec = dict(stem=s, approximated='approximated' in man[s], forms=len(rows), depth=max(r['depth'] for r in rows), ti=len(ti),
                       untyped=sum(1 for r in ti if not r['typed']), one=sum(1 for r in ti if r['one']), empty=sum(1 for r in ti if r['empty']), unk=sorted(unk),
                       tif=[[r['line'], r['depth'], int(r['root']), r['shape'], r['exact']] for r in ti])
            f.write(json.dumps(rec) + '\n')
            f.flush()
            n += 1
    left = len(todo) - n
    print('train stems written', n, 'left', left, 'secs', round(time.time() - T0, 1), flush=True)
    if left:
        return
    tr = read_jsonl(TRAIN_OUT)
    c_shape, c_exact = collections.Counter(), collections.Counter()
    for r in tr:
        c_shape.update({x[3] for x in r['tif']})
        c_exact.update({x[4] for x in r['tif']})
    # the 59 tasks, in memory
    tasks = [json.loads(l) for l in open(TASKS)]
    bits = {}
    for l in open(BITS):
        r = json.loads(l)
        bits[r['task']] = r
    done = {r['task'] for r in read_jsonl(ROWS_OUT)}
    an = {}
    for t in tasks:
        text = open(FLAT + t['task'] + '.arclog').read()
        an[t['task']] = (text, analyze(text, reg))
    t_shape, t_exact = collections.defaultdict(set), collections.defaultdict(set)
    for task, (text, (rows, unk)) in an.items():
        for r in rows:
            if r['ti']:
                t_shape[r['shape']].add(task)
                t_exact[r['exact']].add(task)
    tstems = set(train)
    wrote = 0
    with open(ROWS_OUT, 'a') as f:
        for t in tasks:
            if t['task'] in done or time.time() - T0 > LIMIT:
                continue
            text, (rows, unk) = an[t['task']]
            b = bits[t['task']]
            sha = hashlib.sha256('\n'.join(text.splitlines()).encode()).hexdigest()[:16]
            ok = sha == b['base_sha']
            bl = {x['line']: x for x in b['forms']}
            own = 1 if t['task'] in tstems else 0  # a task's own stem is left out of its counts
            for r in rows:
                bx = bl.get(r['line'])
                f.write(json.dumps(dict(
                    task=t['task'], set='37' if t['source'] == 'eval-37' else 'ramp', line=r['line'], kind=r['kind'], depth=r['depth'], reads=r['reads'],
                    ti=r['ti'], root_ti=r['root'], literal=r['literal'], bits=(bx['bits'] if ok and bx else None), bits_kind=(bx['kind'] if bx else None), base_ok=ok,
                    typed=r['typed'], one=r['one'], empty=r['empty'], shape=r['shape'], exact=r['exact'],
                    train_shape=c_shape[r['shape']] - own if r['ti'] else None, train_exact=c_exact[r['exact']] - own if r['ti'] else None,
                    tasks_shape=len(t_shape[r['shape']]) if r['ti'] else None, tasks_exact=len(t_exact[r['exact']]) if r['ti'] else None)) + '\n')
            f.flush()
            wrote += 1
    left = len([t for t in tasks if t['task'] not in done]) - wrote
    print('task rows written', wrote, 'left', left, 'secs', round(time.time() - T0, 1), flush=True)
    if left:
        return
    build(tr, read_jsonl(ROWS_OUT), tasks, bits, an, man)
    print('done', round(time.time() - T0, 1), flush=True)


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    main()
