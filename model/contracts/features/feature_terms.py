"""Model input layer: the term of each feature, which is what a model reads of a feature beside its value. A feature that reads a table's rows has the term of its schema (grammar.py). A feature that
reads the program's text, or the task's other assignments, has a term that gives its kind.
"""
import re

from grammar import SCHEMAS

TOKEN = re.compile(r'(?:\w+\.)?⟨c:[^⟩]*⟩')
TABLE = re.compile(r'⟨t:[^⟩]*⟩')
OTHER_KINDS = ((re.compile(r' (origin kinds|copy steps|from the input|from the train outputs|from a task parameter)$|^(columns of \w+ origin|every column is a copy|some column from the train outputs|some column from a task parameter)$'), 'provenance'),
               (re.compile(r' (relation atoms|joins|alternatives|alternatives bind it from different sources|under a NOT|under an ALL|(computed|tested) by \w+|compared by \S+|made equal to (zero|another variable))$|^(relation atoms|lib atoms|comparisons|NOTs|ALLs|ORs|joined variables|reads one table twice|variables not at a column)$| (shares an atom with|interchangeable with) C$'), 'program dependence'),
               (re.compile(r'^(duplicate of a relation it reads|projection of a relation it reads|functional extension of a relation it reads|Cartesian product|degenerate|selectivity)$'), 'relational structure'),
               (re.compile(r'^(output claims held|input claims held|output claims that no earlier table holds|input claims that no earlier table holds|first table where .*|changed cells (that|whose output color) no earlier table .*|steps from the input grid|tables before it)$'), 'program order'),
               (re.compile(r'( across assignments| at every assignment| at some assignment| at this assignment alone| with these rows, proportion| vs the other assignments|assignments of its table|across assignments, proportion)$'), 'over assignments'),
               (re.compile(r'the other train examples'), 'over examples'))


def template(feature):
    """A feature's name with each column as C and each other table as T."""
    return TABLE.sub('T', TOKEN.sub('C', feature))


def schema_terms():
    """{template: {'term', 'reads'}} of the schemas of the library."""
    out = {}
    for r in SCHEMAS:
        entry = dict(term=r.semantic_term(), reads=sorted(r.reads()))
        out.setdefault(r.template(), entry)
    return out


_terms = None


def term_of(feature):
    """The term of a feature's name, as a tree of tuples."""
    global _terms
    if _terms is None:
        _terms = schema_terms()
    t = template(feature)
    held = _terms.get(t)
    if held is not None:
        return held['term']
    for pattern, kind in OTHER_KINDS:
        if pattern.search(t):
            return (kind, t)
    return ('unclassified', t)
