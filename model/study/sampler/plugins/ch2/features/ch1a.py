"""ch1a: echo features and column-from-the-end features, written against choicefeat.mask_row rows.

A1  A clause that uses a relation again names the same number of columns, and the same column types in the same order, as
    its previous atom of that relation (derived relations: 83 of 96 repeated atoms name exactly the same column set).
    keys: a1_has_prev, a1_stop_at_nprev, a1_stop_before_nprev, a1_col_below_nprev, a1_col_beyond_nprev, a1_type_echo,
          a1_type_clash, a1_name_in_prev
A2  A value repeats the previous same-relation atom's value at the same place: a column that was fresh before is fresh again
    or the same label again (rarely another label); a column that read a label before is rarely fresh, and reads the same
    label or a newer label of its type.
    keys: a2_has_prev, a2_fresh_pfresh, a2_fresh_pread, a2_same_pfresh, a2_same_pread, a2_shift, a2_newer_same_type,
          a2_other_pfresh, a2_other_pread, a2_zero_pzero
A3  A derived relation of 4 or more columns has its last column named in about 2 of 3 uses (the geometric share by position
    undervalues it); the first column is named about as often as any other.
    keys: a3_arity, a3_from_end, a3_is_last, a3_last_open, a3_arity_ge4_last, a3_last_arity
"""
import re
import sys

try:
    import choicefeat as cf
except ImportError:  # the sampler directory is not on the path
    sys.path.insert(0, '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/sampler')
    import choicefeat as cf

_TOK = re.compile(r'\(|\)|[^\s()]+')
_CACHE = {}


def _parse(s):
    """Parse an atom string (balanced or cut off) into nested lists of tokens."""
    hit = _CACHE.get(s)
    if hit is not None:
        return hit
    root = []
    stack = [root]
    for t in _TOK.findall(s):
        if t == '(':
            n = []
            stack[-1].append(n)
            stack.append(n)
        elif t == ')':
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1].append(t)
    atom = root[0] if root and isinstance(root[0], list) else []
    if atom and atom[0] == 'NOT' and len(atom) > 1 and isinstance(atom[1], list):
        atom = atom[1]
    if len(_CACHE) > 20000:
        _CACHE.clear()
    _CACHE[s] = atom
    return atom


def _rel(atom):
    return atom[0] if atom and isinstance(atom[0], str) else None


def _is_col(x):
    return isinstance(x, list) and x and isinstance(x[0], str) and x[0].startswith(':')


def _leaves(x, out):
    for y in x:
        if isinstance(y, list):
            _leaves(y, out)
        elif isinstance(y, str) and not y.startswith(':') and y != 'NOT':
            out.append(y)
    return out


def _topcols(atom):
    return [x for x in atom[1:] if _is_col(x)]


def _prev_atom(row, rel):
    for a in reversed(row.get('prefix') or []):
        p = _parse(a)
        if _rel(p) == rel:
            return p
    return None


def _label_index(tok):
    return int(tok[1:]) if tok[:1] == 'L' and tok[1:].isdigit() else None


def _f_cols(row, o, d):
    if o['kind'] not in ('column', 'stop'):
        return
    cur = _parse(row.get('text') or '')
    rel = _rel(cur)
    rt = row.get('rtypes') or []
    named = [c for c in _topcols(cur)]
    m = len(named)
    # a3: last column
    cols = [int(x['tok'][1:]) for x in row['options'] if x['kind'] == 'column']
    nameds = []
    for c in named:
        try:
            nameds.append(int(c[0][1:]))
        except ValueError:
            pass
    arity = len(rt) if rt else (max(cols + nameds) + 1 if (cols or nameds) else 0)
    if arity:
        d['a3_arity'] = float(arity)
    if o['kind'] == 'column' and arity:
        j = int(o['tok'][1:])
        last = j == arity - 1
        d['a3_from_end'] = float(arity - 1 - j)
        d['a3_is_last'] = float(last)
        d['a3_last_open'] = float(last and (arity - 1) not in nameds)
        d['a3_arity_ge4_last'] = float(last and arity >= 4)
        d['a3_last_arity'] = float(arity if last else 0)
    # a1: echo of the previous atom of the same relation
    prev = _prev_atom(row, rel) if rel else None
    if prev is None:
        return
    pcols = _topcols(prev)
    npv = len(pcols)
    d['a1_has_prev'] = 1.0
    if o['kind'] == 'stop':
        d['a1_stop_at_nprev'] = float(m == npv)
        d['a1_stop_before_nprev'] = float(m < npv)
        return
    d['a1_col_below_nprev'] = float(m < npv)
    d['a1_col_beyond_nprev'] = float(m >= npv)
    if o.get('name'):
        d['a1_name_in_prev'] = float(any(c[0] == ':' + o['name'] for c in pcols))
    t = o.get('ctype')
    if t and m < npv:
        st = dict(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
        lv = _leaves(pcols[m], [])
        pt = st.get(lv[0].lstrip('*')) if lv else None
        if pt:
            d['a1_type_echo' if cf.compat(pt, t) else 'a1_type_clash'] = 1.0


def _f_val(row, o, d):
    if o['kind'] not in ('fresh', 'zero', 'label'):
        return
    cur = _parse(row.get('text') or '')
    rel = _rel(cur)
    prev = _prev_atom(row, rel) if rel else None
    if prev is None:
        return
    pl = _leaves(prev[1:], [])
    j = len(_leaves(cur[1:], []))
    pv = None
    if row['phase'] == 'val' and row.get('col'):
        for c in _topcols(prev):
            if c[0] == ':' + row['col']:
                lv = _leaves(c, [])
                pv = lv[0] if lv else None
                break
    elif j < len(pl):
        pv = pl[j]
    if pv is None:
        return
    d['a2_has_prev'] = 1.0
    pfresh = pv.startswith('*')
    pname = pv.lstrip('*')
    kind = o['kind']
    if kind == 'zero':
        d['a2_zero_pzero'] = float(pname == '0')
        return
    if pname == '0':
        return
    if kind == 'fresh':
        d['a2_fresh_pfresh' if pfresh else 'a2_fresh_pread'] = 1.0
        return
    c = cf.context(row)
    i = int(o['tok'][1:])
    created = c['created']
    name = created[i] if i < len(created) else None
    if name is None:
        return
    if name == pname:
        d['a2_same_pfresh' if pfresh else 'a2_same_pread'] = 1.0
        return
    d['a2_other_pfresh' if pfresh else 'a2_other_pread'] = 1.0
    if any(x.lstrip('*') == name for x in pl):
        d['a2_shift'] = 1.0
    if pname in created and created.index(pname) < i:
        st = dict(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
        a, b = st.get(pname), st.get(name)
        if a and b and cf.compat(a, b):
            d['a2_newer_same_type'] = 1.0


def ch1a(row, o):
    d = {}
    ph = row.get('phase')
    if ph == 'cols':
        _f_cols(row, o, d)
    elif ph in ('val', 'fval'):
        _f_val(row, o, d)
    return d


FEATURE_FUNCS = {'ch1a': ch1a}
