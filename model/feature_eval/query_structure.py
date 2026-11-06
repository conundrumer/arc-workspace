"""What a query's text says, with no table content: its atom kinds, its label structure, and how
recent the relations it reads are. How a site is spelled, as `D` or `(:D D)`, enters nothing."""
import re
from collections import Counter

TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()"]+')
CONSTRAINTS = {'=', '!=', '<', '<=', '>', '>='}
LOGIC = {'NOT', 'OR', 'IF', 'ALL'}
DEFINING = {'RULE', 'DET', 'INIT', 'DET_OR_RULE', 'RULE_OR_DET', 'CHOOSE', 'RIGID_DET', 'DEMO_RULE', 'DEMONSTRATED'}
LABEL_STRUCTURE = {'zeros', 'fresh', 'marked', 'labels', 'labels_once', 'labels_joined'}


def parse_forms(text):
    """The top-level forms of a program's text, as nested lists of tokens."""
    stack, out = [], []
    for token in TOKEN.findall(text):
        if token == '(':
            stack.append([])
        elif token == ')':
            done = stack.pop()
            (stack[-1] if stack else out).append(done)
        elif stack:
            stack[-1].append(token)
    return out


class Reader:
    """Counts what one form holds."""

    def __init__(self):
        self.bag = Counter()
        self.labels = Counter()
        self.reads = []

    def site(self, node):
        if isinstance(node, str):
            if node == '0':
                self.bag['zeros'] += 1
            elif node.startswith('*'):
                self.bag['fresh'] += 1
                self.labels[node[1:]] += 1
            elif node.startswith('^'):
                self.bag['marked'] += 1
                self.labels[node[1:]] += 1
            elif not node.startswith(':'):
                self.labels[node] += 1
            return
        for part in node[1:] if node and isinstance(node[0], str) and node[0].startswith(':') else node:
            self.site(part)

    def atom(self, node):
        if isinstance(node, str) or not node:
            return
        head = node[0]
        if not isinstance(head, str):
            for part in node:
                self.atom(part)
            return
        if head in LOGIC:
            self.bag['logic:' + head] += 1
            for part in node[1:]:
                self.atom(part)
            return
        self.bag['atoms'] += 1
        if head in CONSTRAINTS:
            self.bag['constraint:' + head] += 1
        elif head.startswith('&'):
            self.reads.append(head)
        else:
            self.bag['relation:' + head] += 1
        for part in node[1:]:
            self.site(part)

    def form(self, form):
        head = form[0]
        self.bag['form:' + head] += 1
        if head == 'INIT':
            self.bag['component:' + form[2]] += 1
            for clause in form[3:]:
                if clause[0] == 'key':
                    self.bag['clause:key'] += 1
                    for atom in clause[1]:
                        self.atom(atom)
                    rest = clause[2:]
                else:
                    rest = [clause]
                for held in rest:
                    self.bag['input:' + held[0]] += 1
                    if len(held) > 1:
                        self.site(held[1])
                    for atom in held[2:]:
                        self.atom(atom)
            return
        for part in form[2:]:
            if isinstance(part, str):
                self.bag['proposer:' + part] += 1
            else:
                self.atom(part)


def relation_of(read):
    return read.split('.')[0]


def query_features(forms, at, gold_forms):
    """A query's features: only the prefix before the query and the query's own form enter."""
    reader = Reader()
    reader.form(forms[at])
    out = Counter(reader.bag)
    defined = {}
    for index, form in enumerate(gold_forms[:at]):
        if form and form[0] in DEFINING and len(form) > 1:
            defined[form[1]] = (index, form[0])
    read_before = set()
    for form in gold_forms[:at]:
        earlier = Reader()
        earlier.form(form)
        read_before.update(relation_of(read) for read in earlier.reads)
    pending = [name for name in defined if name not in read_before]
    distances = []
    for read in reader.reads:
        held = defined.get(relation_of(read))
        if held is None:
            out['read_unknown'] += 1
            continue
        distances.append(at - held[0])
        out['read_of:' + held[1]] += 1
        if read != relation_of(read):
            out['read_port'] += 1
    read_names = {relation_of(read) for read in reader.reads}
    out['position'] = at
    out['prefix_relations'] = len(defined)
    out['reads'] = len(reader.reads)
    out['reads_distinct'] = len(read_names)
    if distances:
        out['read_min'] = min(distances)
        out['read_max'] = max(distances)
        out['read_mean'] = sum(distances) / len(distances)
        out['read_previous'] = int(1 in distances)
    out['pending'] = len(pending)
    out['pending_read'] = sum(name in read_names for name in pending)
    out['pending_left'] = out['pending'] - out['pending_read']
    out['labels'] = len(reader.labels)
    out['labels_once'] = sum(count == 1 for count in reader.labels.values())
    out['labels_joined'] = sum(count >= 2 for count in reader.labels.values())
    return out


def base_features(forms, at, gold_forms, types, task_level):
    """A candidate's features with no table content."""
    out = query_features(forms, at, gold_forms)
    out['columns'] = len(types)
    out['task_level'] = int(bool(task_level))
    for ty in types:
        out['type:' + ty] += 1
    return out
