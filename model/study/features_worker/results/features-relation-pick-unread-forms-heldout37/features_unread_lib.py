"""What the scripts of this record share: a gold program's forms, which form reads which, and the unread sets. Stdlib only.

A form is a line of gold that declares a relation head: every kind but OUT. Slots: the census names an atom's relation by its slot, &r<n>, and a form with head &r<h> owns the slots from h up to the next form's head, so the text alone gives a slot's form.

The sets at a pick of form j, atom a, each cut to the forms in scope (the forms before j, or for the parents scope the forms that j reads, directly or not):
- unread_gold: read by no form of gold, form j included. A target is never inside, as form j reads it.
- unread_later: read by no form of gold other than form j. It reads forms after j.
- unread_before: read by no form before j. This is the set `unread_before` of the record features-init-residual-bits-split-74forms.
- unread_so_far: read by no form before j, and by no atom of form j before atom a.
"""
import bisect
import math
import re

HEAD = re.compile(r'^\((\w+)\s+(&[A-Za-z_0-9]+)')
NAME = re.compile(r'&[A-Za-z_0-9]+')
ATOM = re.compile(r'\((?:NOT \()?([^\s()]+)')
SETS = ('unread_gold', 'unread_later', 'unread_before', 'unread_so_far')
DIR = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
W = DIR + 'sampler/sampler-worker/'
BASE = W + 'sampler-helper-forms/gold-v3-helper-forms-a036da074/'
RANK = DIR + 'features-worker/results/features-relation-pick-rank-context-rows-heldout37/'
RUN = DIR + 'sampler/search-worker/runs/search-pool-factored-priors-heldout35-600s-ship7/'
ARMS = ('control_search', 'factored_search')
NOT_IN_RUN = ('269e22fb', 'cbebaa4b')
BAR = 25.0


def held_tasks():
    return open(W + 'held/tasks.txt').read().split()


def lines_of(sexp):
    return [x for x in sexp.splitlines() if x.strip()]


class Gold:
    """The forms of one gold program, and who reads whom."""

    def __init__(self, lines):
        self.lines = lines
        self.kind, self.head = {}, {}  # line index -> kind, head name
        for i, x in enumerate(lines):
            m = HEAD.match(x)
            self.kind[i] = x.split()[0].lstrip('(')
            if m:
                self.head[i] = m[2]
        self.forms = sorted(self.head)
        self.line_of = {h: i for i, h in self.head.items()}
        nums = [(int(self.head[i][2:]), i) for i in self.forms if re.fullmatch(r'&r\d+', self.head[i])]
        nums.sort()
        self.num, self.num_line = [n for n, _ in nums], [i for _, i in nums]
        self.reads = {}  # line index -> [line index of each read of an earlier form, in text order, with repeats]
        for i, x in enumerate(lines):
            own = self.head.get(i)
            body = x[HEAD.match(x).end():] if own else x
            self.reads[i] = [self.line_of[n] for n in NAME.findall(body) if n in self.line_of and n != own]

    def form_of_slot(self, name):
        """The line of the form that owns slot name, or None for a name that is no slot."""
        if not re.fullmatch(r'&r\d+', name or ''):
            return None
        k = bisect.bisect_right(self.num, int(name[2:])) - 1
        return self.num_line[k] if k >= 0 else None

    def slots(self, line):
        """The count of slots that the form at line owns; the last form has no next head, so it reads None."""
        k = self.num_line.index(line)
        return self.num[k + 1] - self.num[k] if k + 1 < len(self.num) else None

    def parents(self, j):
        """The forms before j that j reads, directly or not: frontier_q.parents of the census, on this class's reads."""
        got, todo = set(), [j]
        while todo:
            for r in self.reads[todo.pop()]:
                if r < j and r not in got:
                    got.add(r)
                    todo.append(r)
        return sorted(got)

    def read_set(self, skip=None, below=None):
        """The forms that some form reads: every form but skip, and only forms before line below where below is given."""
        out = set()
        for i, rs in self.reads.items():
            if i != skip and (below is None or i < below):
                out.update(rs)
        return out


class Sets:
    """The status of the forms before form j, once per form; `at` applies the earlier atoms of the form."""

    def __init__(self, gold, j):
        self.scope = [i for i in gold.forms if i < j]
        self.parents = gold.parents(j)
        whole = gold.read_set()
        others = gold.read_set(skip=j)
        before = gold.read_set(below=j)
        self.gold = [i for i in self.scope if i not in whole]
        self.later = [i for i in self.scope if i not in others]
        self.before = [i for i in self.scope if i not in before]

    def at(self, seen):
        """{set name: list of forms in the scope of all earlier forms} at a pick after the atoms that read the forms of seen."""
        return dict(unread_gold=self.gold, unread_later=self.later, unread_before=self.before, unread_so_far=[i for i in self.before if i not in seen])


def relation_of(text):
    """The relation name of an atom's text and whether the text has NOT."""
    m = ATOM.match(text)
    return (m[1] if m else None), text.startswith('(NOT')


def mix_bits(rel_bits, w, n_set, in_set):
    """Bits of a pick under the mixture: weight w uniform over a set of n_set options, 1-w on the steered prior of rel_bits. With an empty set the pick stays as it is."""
    if not n_set:
        return rel_bits
    p = 2.0 ** -rel_bits
    q = (1 - w) * p + (w / n_set if in_set else 0.0)
    return -math.log2(q)
