"""The part of backward_edges.py that the find at the pick (item 19) uses, copied as it stands: the lib signature table, the atom parser, the sites of an atom's arguments and the type of a site.
The rest of the source (edges from OUT, reader bodies, depth) reads a gold program's forms in written order and has no use here.
"""
import collections
import re

SIG = '/Users/davidlu/code/arc-workspace/src/arclog_convert/lib-signature.dl'
TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+')
ALIAS = {'input': 'in', 'ex_input': 'ex_in', 'ex_output': 'ex_out'}
CMP = ('=', '!=', '<', '<=', '>', '>=')


def sig_table():
    """{relation name: {lower-case column name: type}} of the lib signature."""
    out = {}
    for x in open(SIG):
        m = re.match(r'\s*\.decl\s+(\w+)\((.*?)\)', x)
        if m:
            cols = {}
            for c in m.group(2).split(','):
                if ':' in c:
                    a, b = c.split(':')
                    cols[a.strip().lower()] = b.strip()
            out[m.group(1)] = cols
    return out


SIGNATURE = sig_table()


def parse(text):
    toks = TOKEN.findall(text)
    stack = [[]]
    for t in toks:
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop()
            stack[-1].append(x)
        else:
            stack[-1].append(t)
    return stack[0][0] if stack[0] else []


def strip(label):
    return label.lstrip('*^')


def sites_of(args):
    """[(column name or None, label, mark)] of an atom's arguments. A record column's fields are sites of their own."""
    out = []

    def one(col, v):
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0].startswith(':'):
                rest = v[1:]
                for w in rest:
                    one(v[0][1:], w)
            else:
                for w in v:
                    one(col, w)
        else:
            if v == '0' or v.lstrip('-').isdigit():
                out.append((col, None, '0'))
            else:
                out.append((col, strip(v), v[0] if v[0] in '*^' else ''))

    for a in args:
        if isinstance(a, list):
            if a and isinstance(a[0], str) and a[0].startswith(':'):
                for w in a[1:]:
                    one(a[0][1:], w)
            else:
                one(None, a)
        else:
            one(None, a)
    return out


def col_type(atom, site):
    """The type of a site from the lib's signature, or None."""
    c = SIGNATURE.get(ALIAS.get(atom['name'], atom['name']))
    if c is None:
        return None
    k = (site[0] or site[1] or '').lower()
    return c.get(k)


def norm_type(t):
    return 'Position' if t == 'Box' else t
