"""Check arclog, arcdata and arcscene files against the rules of
docs/arclog/arclog.md, docs/arclog/constraints.md, docs/arclog/rigid.md, docs/arclog/arcdata.md and
docs/arcscene.md that the file decides alone, with the files it imports.

    uv run python -m arclog_convert.lint [--all] [FILE ...]

With no file, checks every arclog and arcdata file under gen/ of
`arclog_convert.out` and every arcscene file directly under
`arclog_convert.out`. An arcdata file reads the names
of the arclog file of its stem, and an arcscene file reads the arclog and
arcdata files of its stem under gen/. A file under
gen/ is read through `arclog_convert.readback.read_checked`; one that is not current gets the violation `stale`.
Prints each
violation as `file:line: code: message`, four per code over more than 20
files unless --all, then a count per code. The reader of the text
(`arclog_convert.lint_read`) and the analysis of its alternatives
(`arclog_convert.lint_alts`) are modules of their own.
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from arclog_convert import libmap, out
from arclog_convert.readback import Stale, read_checked
from arclog_convert.lint_alts import (
    CLAIMS, DECL_HEADS, Placed, alt_blocks, alt_repeats, alts_map, claims_of, placements, reads, restated_outs, unstated_combinations)
from arclog_convert.lint_read import L, Str, Sym, flat, leaves, read, walk
from arclog_convert.lint_source import bare_read_source
from arclog_convert.lib import ALGEBRA_MODES, DET_COLS, PROPOSER_COLS, SIGNATURE, Lib, pascal, takes_set_mark

GEN = out() / "gen"


def read_file(path: Path) -> str:
    """The text of the file `path`: through `read_checked` where it stands under `GEN`, and `read_text` elsewhere."""
    return read_checked(path) if GEN.resolve() in path.resolve().parents else path.read_text()


FACTS = {"input": ["P", "Col"], "ex_input": ["E", "P", "Col"], "ex_output": ["E", "P", "Col"]}
OPS = {"=", "!=", "<", "<=", ">", ">="}
FORMS = {"OR", "IF", "ALL", "NOT"}
SCENE_BUILTINS = {"ex": ["E"], "color": ["C"], "number": ["N"], "ident": ["Id"]}
MARKS = {"ONE", "SET"}   # the marks a clause ends in
POSE_LIB = {"pose_difference": ["A", "B", "D"]}   # the lib relations on a Pose: Souffle has no Pose, so the signature has none


# ---------------------------------------------------------------- relations

LIB = Lib(SIGNATURE)


def lib_cols(name: str) -> set[str] | None:
    if name in FACTS:
        return set(FACTS[name])
    if name in POSE_LIB:
        return set(POSE_LIB[name])
    if name in LIB.top:
        return {pascal(n) for n, _ in LIB.top[name]}
    return None


def comp_cols(comp: str, rel: str) -> tuple[set[str], set[str]] | None:
    """The fixed-type and the type-parameter columns of a component's
    relation, `key` first among the latter."""
    if comp not in LIB.comps:
        return None
    tps, rels = LIB.relations(comp)
    for r in rels:
        if r.name == rel:
            fixed = {c.name for c in r.cols if not c.tparam and c.name != "key"}
            tparam = {c.name for c in r.cols if c.tparam} | {"key"}
            return fixed, tparam
    return None


# ---------------------------------------------------------------- scopes


@dataclass
class Scope:
    parent: Scope | None
    made: dict[str, int] = field(default_factory=dict)   # label -> line
    pending: set[str] = field(default_factory=set)       # exports of an earlier branch
    named: set[str] = field(default_factory=set)         # pending labels this branch names
    key_mode: bool = False
    keys: list[str] = field(default_factory=list)
    alias: dict[str, str] = field(default_factory=dict)  # label -> its renamed label
    made_at: dict[str, tuple] = field(default_factory=dict)  # label -> (atom, the site that made it)
    kind: str = "top"   # top | first | later | test | then | else | all | key
    eq_made: dict[str, int] = field(default_factory=dict)    # label -> line of the `=` that made it
    union: bool = False   # a branch of an OR that is a whole body
    eq_same: dict[str, tuple] = field(default_factory=dict)  # label -> (line, message): stands unless the union exports it

    def maker(self, x: str):
        s = self
        while s:
            if x in s.made_at:
                return s.made_at[x] + (s,)
            if x in s.made:
                return None
            s = s.parent
        return None

    def resolve(self, x: str) -> str:
        s = self
        while s:
            if x in s.alias:
                return s.alias[x]
            s = s.parent
        return x

    def visible(self, x: str) -> bool:
        s = self
        while s:
            if x in s.made:
                return True
            s = s.parent
        return False

    def pending_here(self, x: str) -> Scope | None:
        s = self
        while s:
            if x in s.pending:
                return s
            if x in s.made:
                return None
            s = s.parent
        return None


class Linter:
    def __init__(self, path: Path, text: str | None = None, pre: bool = True):
        self.path = path
        self.text = read_file(path) if text is None else text
        # a first pass over the file, for the columns each alt's blocks declare
        self.pre: Linter | None = None
        if pre and path.suffix == ".arclog":
            self.pre = Linter(path, self.text, pre=False)
            self.pre.run()
        self.errs: list[tuple[int, str, str]] = []
        self.fixes: dict[int, tuple[int, str]] = {}   # pos -> (length, replacement)
        self.declared: dict[str, object] = {}   # &name -> column set or ("comp", Comp)
        self.cols: dict[str, set[str]] = defaultdict(set)
        self.side: dict[str, str] = {}
        self.inst_comp: dict[str, str] = {}
        self.all_names: set[str] = set()
        self.concept_names: set[str] = set()
        self.block: dict[str, int] = {}   # relation -> line of its clause in the current block
        self.rigid_parts: dict[str, set[str]] = {}   # a RIGID_DET form -> the parts its atoms name, and pose
        # relation -> per clause, the columns a top-level (= *X 0) makes, with its line
        self.zero_cols: dict[str, list[dict[str, int]]] = defaultdict(list)
        self.or_lines: set[tuple[int, str]] = set()   # (block, relation) of each _OR_ form
        self.scene = path.suffix == ".arcscene"
        self.imported: Linter | None = None   # a scene's arclog file
        self.choose_info: dict[str, tuple[list[str], set[str]]] = {}   # a CHOOSE's key labels and from labels
        self.chosen: set[str] = set()   # the relations a CHOOSE or ONE marks pick
        self.part_cols: dict[str, dict[str, set[str] | None]] = {}   # a rigid form -> part -> its columns
        self.rigid_keyed: dict[str, bool] = {}
        self.stored: set[str] = set()   # the params: a proposer's DET, a DET_OR_RULE line, a RIGID_DET's parts
        self.params: set[str] = set()   # the param names of the arcdata file
        self.set_marked: dict[str, int] = {}   # each relation whose clause ends in `(SET)`, and its line
        self.decl_cols: dict[str, list[set[str]]] = defaultdict(list)   # each declaration's own columns, in order
        self.placed: list[Placed] = []
        self.alt_chain: list[str] = []   # the ALT blocks open at the current form, outermost first
        # (alts, relation) -> the columns of a declaration in the blocks of those alts, over the whole file
        self.chain_cols: dict[tuple[frozenset[str], str], set[str]] = defaultdict(set)

    def err(self, line: int, code: str, msg: str) -> None:
        self.errs.append((line, code, msg))

    # ---- program

    def run(self) -> None:
        try:
            forms = read(self.text)
        except SyntaxError as e:
            self.err(0, "syntax", str(e))
            return
        if self.scene:
            arclog = GEN / f"{self.path.stem}.arclog"
            if arclog.exists():
                self.imported = Linter(arclog)
                self.imported.run()
                data = arclog.with_suffix(".arcdata")
                if data.exists():
                    try:
                        self.imported.params = {x.items[1].text for x in read(read_file(data))
                                                if isinstance(x, L) and x.head == "param" and len(x.items) > 1
                                                and isinstance(x.items[1], Sym)}
                    except SyntaxError:
                        pass
            else:
                self.err(0, "scene-arclog", f"no arclog file {arclog.name} under gen/")
        self.prescan(forms)
        self.forms(forms, alt=False)
        self.records(forms)
        structure(self, forms)
        if not self.scene:
            cycles(self, self.placed)
            safety(self, forms)
        for name, clauses in self.zero_cols.items():
            for x, line in clauses[0].items():
                if all(x in z for z in clauses):
                    self.err(line, "head-zero", f"(= *{x} 0): {name} is 0 at column {x} in every clause, "
                             "so the column is dropped")

    def prescan(self, forms, alt: bool = False) -> None:
        """Every relation name the file declares, for reads inside alts, and
        the names the concept program declares."""
        for f in forms:
            if not isinstance(f, L):
                continue
            if f.head in ("RULE", "DET", "INIT", "CHOOSE", "RIGID_DET", "RIGID", "DEMONSTRATED", "DET_OR_RULE",
                          "RULE_OR_DET") \
                    and len(f.items) > 1 and isinstance(f.items[1], Sym):
                self.all_names.add(f.items[1].text)
                if not alt:
                    self.concept_names.add(f.items[1].text)
            self.prescan(f.items[1:], alt or f.head == "ALTS")

    def forms(self, forms, alt: bool) -> None:
        for f in forms:
            if isinstance(f, L):
                self.form(f, alt)

    def form(self, f: L, alt: bool) -> None:
        h = f.head
        if h in CLAIMS:
            if len(f.items) < 2 or not isinstance(f.items[1], Sym):
                self.err(f.line, "claim", f"{h} without a slug")
            self.forms(f.items[2:], alt)
        elif h == "ALTS" and self.scene:
            it = f.items
            if len(it) < 2 or not (isinstance(it[1], Sym) and it[1].text.startswith("$")):
                self.err(f.line, "alts", "ALTS is $name, then ALT blocks")
            for a in it[2:]:
                if not (isinstance(a, L) and a.head == "ALT"):
                    self.err(getattr(a, "line", f.line), "alts", "an ALTS form holds ALT blocks only")
            self.forms(it[2:], True)
        elif h == "ALL" and self.scene:
            self.constraint_form(f, alt)
        elif h == "RENDER" and self.scene:
            self.render(f, alt)
        elif h == "RIGID" and self.scene:
            self.rigid_group(f, alt)
        elif h == "ALTS":
            it = f.items
            if len(it) < 4 or not (isinstance(it[1], Sym) and it[1].text.startswith("$")
                                   and isinstance(it[2], Str) and isinstance(it[3], Sym)
                                   and it[3].text.startswith("$")):
                self.err(f.line, "alts", "ALTS is $name, gloss, $Concept, then ALT blocks")
            self.gloss(f)
            for a in it[4:]:
                if not (isinstance(a, L) and a.head == "ALT"):
                    self.err(getattr(a, "line", f.line), "alts", "an ALTS form holds ALT blocks only")
            self.forms(it[4:], True)
        elif h == "ALT":
            if len(f.items) < 2 or not (isinstance(f.items[1], Sym) and f.items[1].text.startswith("$")):
                self.err(f.line, "alts", "ALT without a $name")
            outer, self.block = self.block, {}
            self.alt_chain.append(f.items[1].text if len(f.items) > 1 and isinstance(f.items[1], Sym) else "")
            self.forms(f.items[2:], True)
            self.alt_chain.pop()
            self.block = outer
        elif h == "APPROXIMATED":
            pass
        elif h in ("RULE", "DET"):
            self.clause(f, h, alt)
        elif h in ("RULE_OR_DET", "DET_OR_RULE") and any(isinstance(x, L) and x.head not in MARKS
                                                         for x in f.items[or_start(f):]):
            # the name, a gloss where the solver states one, a DET_OR_RULE's
            # proposers, then the body of the side the program derives
            self.gloss(f)
            k = or_start(f)
            if len(f.items) < 2 or not isinstance(f.items[1], Sym):
                self.err(f.line, "det-or-rule", f"({h} &name [\"gloss\"] <proposer> ... <body>)")
                return
            props = [x for x in f.items[k:] if isinstance(x, Sym)]
            if h == "RULE_OR_DET" and props:
                self.err(f.line, "det-or-rule", f"{f.items[1].text}: a RULE_OR_DET takes no proposer")
            elif h == "DET_OR_RULE" and not props:
                self.err(f.line, "det-or-rule", f"{f.items[1].text}: no proposer")
            for x in props:
                if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", x.text):
                    self.err(f.line, "proposer", f"{x.text} is no proposer name")
            body = [x for x in f.items[k:] if isinstance(x, L)]
            self.stored.add(f.items[1].text)
            self.clause(L([f.items[0], f.items[1], *body], f.line, f.start, f.end), h.split("_")[0], alt,
                        or_line=True)
        elif h in ("DET_OR_RULE", "RULE_OR_DET"):
            # the name, the gloss, then one proposer per derived side, then
            # the ONE marks of a DET_OR_RULE
            self.gloss(f)
            if len(f.items) > 1 and isinstance(f.items[1], Sym):
                self.block_or_line(f.items[1].text, f.line)
            props = f.items[or_start(f):]
            marks = []
            while props and isinstance(props[-1], L) and props[-1].head in MARKS:
                marks.insert(0, props.pop())
            sets = [m for m in marks if m.head == "SET"]
            marks = [m for m in marks if m.head == "ONE"]
            if marks:
                self.chosen.add(f.items[1].text)
            if marks and h == "RULE_OR_DET":
                self.err(f.line, "det-or-rule", f"{f.items[1].text}: a RULE_OR_DET line takes no ONE mark")
            if sets and h == "RULE_OR_DET":
                self.err(f.line, "det-or-rule", f"{f.items[1].text}: a RULE_OR_DET line takes no SET mark")
            if len(f.items) < 2 or not isinstance(f.items[1], Sym):
                self.err(f.line, "det-or-rule", f"({h} &name [\"gloss\"] <proposer> ...)")
            elif h == "RULE_OR_DET" and props:
                self.err(f.line, "det-or-rule", f"{f.items[1].text}: a RULE_OR_DET line takes no proposer")
            elif h == "DET_OR_RULE" and not props:
                self.err(f.line, "det-or-rule", f"{f.items[1].text}: no proposer")
            for x in props:
                if not (isinstance(x, Sym) and re.fullmatch(r"[A-Z][A-Za-z0-9]*", x.text)):
                    self.err(f.line, "proposer", f"{flat(x)} is no proposer name")
                elif x.text not in PROPOSER_COLS:
                    self.err(f.line, "proposer-unknown", f"{x.text}: no proposer of this name is defined beside the lib")
            # the stored side's columns, onto which each proposer's map by position
            known = [[c.name for c in PROPOSER_COLS[x.text]] for x in props
                     if isinstance(x, Sym) and x.text in PROPOSER_COLS]
            if any(len(k) != len(known[0]) for k in known):
                self.err(f.line, "det-or-rule", f"{f.items[1].text}: the proposers give different column counts, "
                         + ", ".join(f"{x.text} {len(PROPOSER_COLS.get(x.text, []))}" for x in props if isinstance(x, Sym)))
            for m in marks:
                for x in m.items[1:]:
                    if not (isinstance(x, Sym) and known and x.text in known[0]):
                        self.err(m.line, "one", f"(ONE ...): {flat(x)} is no column of {f.items[1].text}")
            self.stored.add(f.items[1].text)
            if sets and h == "DET_OR_RULE":
                self.set_mark(f, f.items[1].text, [x.text for x in props if isinstance(x, Sym)], sets)
            # the relation of a line with no body has its first proposer's columns
            self.declare(f.items[1].text, set(known[0]) if known else set(), "DET", f.line)
        elif h == "INIT":
            self.init(f, alt)
        elif h == "CHOOSE":
            self.choose(f, alt)
        elif h == "RIGID_DET":
            self.rigid(f, alt)
        elif h == "OUT":
            self.out(f, alt)
        elif h == "DEMONSTRATED":
            self.demonstrated(f, alt)
        elif h == "DEMO_RULE":
            # the name, or the constructor with a fresh label per field, the
            # rule's text where the solver states one, then the clauses
            outer, self.block = self.block, {}
            k = 3 if len(f.items) > 2 and isinstance(f.items[2], Str) else 2
            head = f.items[1] if len(f.items) > 1 else None
            outer_fields, self.demo_fields = getattr(self, "demo_fields", set()), \
                {t.text[1:] for t in head.items[1:] if isinstance(t, Sym) and t.text[:1] == "*"} \
                if isinstance(head, L) else set()
            self.forms(f.items[k:], alt)
            self.block, self.demo_fields = outer, outer_fields
        else:
            self.err(f.line, "form", f"unknown form {h}")

    def gloss(self, f: L) -> None:
        if len(f.items) > 2 and isinstance(f.items[2], Str) and not f.items[2].text.strip('"').strip():
            self.err(f.line, "empty-gloss", f"{flat(f.items[1])}: the gloss is empty")

    def block_or_line(self, name: str, line: int) -> None:
        """An _OR_ line on a relation: a clause of it in the same block is
        a second form deriving it."""
        if name in self.block:
            self.err(line, "or-line-twice", f"{name} has a clause at line {self.block[name]} of this block "
                     "beside its _OR_ line, which derives it")
        self.block.setdefault(name, line)
        self.or_lines.add((id(self.block), name))

    def set_mark(self, f: L, name: str, props: list[str], marks: list[L]) -> None:
        """Refuses the `(SET)` marks of the clause `f` of `name`, by `props`,
        unless it is one mark with no label, after proposers of one column
        each that are no type-domain proposer. Notes the relation, whose
        `param` form must hold several rows."""
        self.set_marked[name] = f.line
        if len(marks) > 1 or any(len(m.items) > 1 for m in marks):
            self.err(f.line, "set", f"{name}: a clause takes one (SET) mark, which holds no label")
        for p in props:
            if not takes_set_mark(p):
                self.err(f.line, "set", f"{name}: (SET) follows proposers of one column each that are no type-domain "
                         f"proposer, and {p} is not one")

    def declare(self, name: str, cols: set[str], side: str, line: int) -> None:
        if not name.startswith("&"):
            self.err(line, "name", f"declared name {name} lacks &")
        self.declared[name] = True
        self.cols[name] |= cols
        if self.alt_chain:
            self.chain_cols[(frozenset(self.alt_chain), name)] |= cols
        self.decl_cols[name].append(set(cols))
        self.side.setdefault(name, side)

    # ---- clauses

    def clause(self, f: L, side: str, alt: bool, or_line: bool = False) -> None:
        it = f.items
        if len(it) < 2 or not isinstance(it[1], Sym):
            self.err(f.line, "clause", "clause without a name")
            return
        name = it[1].text
        body = it[2:]
        if name in self.block and ((id(self.block), name) in self.or_lines or or_line):
            self.err(f.line, "or-line-twice", f"{name} has an _OR_ line and a clause in this block, "
                     f"at lines {self.block[name]} and {f.line}")
        elif name in self.block:
            self.err(f.line, "clause-twice", f"{name} has a clause at line {self.block[name]} of this block; a union is one clause whose body is an OR")
        self.block.setdefault(name, f.line)
        if or_line:
            self.or_lines.add((id(self.block), name))
        n = len(body)
        while n and isinstance(body[n - 1], L) and body[n - 1].head in MARKS:
            n -= 1
        sets = [m for m in body[n:] if m.head == "SET"]
        body = [*body[:n], *(m for m in body[n:] if m.head == "ONE")]
        if sets and not (side == "DET" and n == 1 and isinstance(body[0], Sym)):
            self.err(f.line, "set", f"{name}: (SET) stands after the proposer of a DET with no body")
        if side == "DET" and n == 1 and isinstance(body[0], Sym):
            if sets:
                self.set_mark(f, name, [body[0].text], sets)
            if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", body[0].text):
                self.err(f.line, "proposer", f"{body[0].text} is no proposer name")
            elif body[0].text not in DET_COLS:
                self.err(f.line, "proposer-unknown", f"{body[0].text}: no proposer or derivation of this name is defined beside the lib")
            if body[n:]:
                self.chosen.add(name)
            self.stored.add(name)
            # the relation of a proposer or a derivation has its columns
            cols = {c.name for c in DET_COLS.get(body[0].text, ())}
            for m in body[n:]:
                for x in m.items[1:]:
                    if not (isinstance(x, Sym) and x.text in cols):
                        self.err(m.line, "one", f"(ONE ...): {flat(x)} is no column of {body[0].text}")
            self.declare(name, cols, side, f.line)
            return
        ctx = Ctx(self, side, alt, own=None, self_name=name)
        ctx.zero_mode = "clause"
        top = Scope(None)
        if name == "&prediction":
            # a demonstrated rule's header makes its field labels
            top.made.update({x: f.line for x in getattr(self, "demo_fields", set())})
        # the order of sites gives no scoping: a label a top-level site
        # makes is in scope across the clause
        for a in body[:n]:
            if isinstance(a, L) and a.head not in FORMS | OPS | {"ONE"}:
                for t in a.items[1:]:
                    for leaf in ([t] if isinstance(t, Sym) else leaves(t)):
                        if leaf.text[:1] == "*":
                            ctx.top_made.add(leaf.text[1:])
        ctx.body(body[:n], top)
        self.zero_cols[name].append(dict(ctx.top_zero))
        cols = set(top.made)
        if body[n:]:
            self.chosen.add(name)
        for m in body[n:]:
            for x in m.items[1:]:
                if not (isinstance(x, Sym) and re.fullmatch(r"[A-Z]\w*", x.text)):
                    self.err(m.line, "one", f"(ONE ...): {flat(x)} is no label")
                elif top.resolve(x.text) not in cols:
                    self.err(m.line, "one", f"(ONE ... {x.text} ...): the clause makes no label {x.text}")
        self.declare(name, cols, side, f.line)

    # ---- record sites

    def records(self, forms) -> None:
        """Every site on a record-valued column names the record's fields by
        projection: each argument is `(:<Field> <label>)`, or the bare label
        where the label is the field's name. The fields of an instance's
        type parameter are the heads of the first projection onto it, and
        the fields of its key are the key's `^` labels."""
        inits = [f for x in forms for f in walk(x)
                 if isinstance(f, L) and f.head == "INIT" and len(f.items) > 2
                 and isinstance(f.items[1], Sym) and isinstance(f.items[2], Sym)]
        types: dict[str, dict[str, dict[str, str]]] = {}   # instance -> relation -> column -> type
        fields: dict[str, dict[str, list[list[str]]]] = defaultdict(lambda: defaultdict(list))   # instance -> type -> each INIT's field names
        heads: list[tuple[str, str, L]] = []                # (instance, input, head site)
        for f in inits:
            name, comp = f.items[1].text, f.items[2].text
            if comp not in LIB.comps:
                continue
            _, rels = LIB.relations(comp)
            types.setdefault(name, {r.name: {c.name: c.type for c in r.cols if c.tparam} for r in rels})
            bound: dict[str, list[str]] = {}   # this INIT's: an instance in two alts has two
            for c in f.items[3:]:
                if not isinstance(c, L):
                    continue
                inputs = c.items[2:] if c.head == "key" else [c]
                if c.head == "key" and len(c.items) > 1:
                    keys: list[str] = []
                    for t in walk(c.items[1]):
                        if isinstance(t, Sym) and t.text[:1] == "^" and t.text[1:] not in keys:
                            keys.append(t.text[1:])
                    bound["key"] = keys
                    fields[name]["key"].append(keys)
                for x in inputs:
                    if not (isinstance(x, L) and x.head and len(x.items) > 1 and isinstance(x.items[1], L)):
                        continue
                    for site in x.items[1].items:
                        if not (isinstance(site, L) and site.head and site.head.startswith(":")):
                            continue
                        t = types[name].get(x.head, {}).get(site.head[1:])
                        if t is None:
                            continue
                        if t not in bound:
                            bound[t] = [a.head[1:] if isinstance(a, L) else a.text.lstrip("*^")
                                        for a in site.items[1:] if isinstance(a, Sym)
                                        or (isinstance(a, L) and a.head and a.head.startswith(":"))]
                            fields[name][t].append(bound[t])
                        else:
                            heads.append((name, x.head, site))
        sites = [(n, r, s_) for n, r, s_ in heads]
        for x in forms:
            for a in walk(x):
                if not (isinstance(a, L) and a.head and a.head.startswith("&") and "." in a.head):
                    continue
                inst, _, out = a.head.partition(".")
                for site in a.items[1:]:
                    if isinstance(site, L) and site.head and site.head.startswith(":"):
                        sites.append((inst, out, site))
        for inst, rel, site in sites:
            col = site.head[1:]
            t = "key" if col == "key" else types.get(inst, {}).get(rel, {}).get(col)
            binds = fields[inst][t] if inst in fields and t else []
            if not binds or any(len(b) < 2 for b in binds):
                continue
            used = [a.text.lstrip("*^") if isinstance(a, Sym) else a.head[1:] for a in site.items[1:]
                    if isinstance(a, Sym) or (isinstance(a, L) and a.head and a.head.startswith(":"))]
            if any(set(used) <= set(b) for b in binds):
                continue
            names = binds[0]
            for arg in site.items[1:]:
                if isinstance(arg, Sym):
                    lab = arg.text.lstrip("*^")
                    if lab not in names:
                        self.err(arg.line, "record-position", f"({site.head} ... {arg.text} ...): {lab} is no field of "
                                 f"{site.head[1:]}, whose fields are {' '.join(names)}; a record's fields are named by "
                                 f"projection, (:<Field> {arg.text})")
                elif isinstance(arg, L) and arg.head and arg.head.startswith(":") and arg.head[1:] not in names:
                    self.err(arg.line, "record-field", f"({site.head} ... {flat(arg)} ...): {site.head[1:]} has no "
                             f"field {arg.head[1:]}; its fields are {' '.join(names)}")

    # ---- instances

    def init(self, f: L, alt: bool) -> None:
        it = f.items
        name, comp = it[1].text, it[2].text if len(it) > 2 and isinstance(it[2], Sym) else None
        if comp not in LIB.comps:
            self.err(f.line, "component", f"unknown component {comp}")
        self.inst_comp[name] = comp
        if not name.startswith("&"):
            self.err(f.line, "name", f"declared name {name} lacks &")
        self.init_order(f, comp)
        self.own_reads(f, name, comp)
        if not alt and not any(isinstance(c, L) for c in it[3:]):
            self.err(f.line, "bare-init", f"{name} has no input in the concept: it declares an empty relation")
        text = flat(f)
        side = "DET" if re.search(r"\((ex_input|ex_output)[\s)]", text) else "ANY"
        ctx = Ctx(self, side, alt, own=name, self_name=name)
        root = Scope(None)
        keyed = False
        for c in it[3:]:
            if not isinstance(c, L):
                self.err(getattr(c, "line", f.line), "instance", "an INIT holds clauses only")
                continue
            if c.head == "key":
                keyed = True
                ctx.keyclause(c, root, lambda inner, scope: ctx.input(inner, scope, comp))
            else:
                ctx.input(c, root, comp, broadcast=keyed)
        seen: dict[str, int] = {}
        for c in it[3:]:
            for x in (c.items[2:] if isinstance(c, L) and c.head == "key" else [c]):
                if isinstance(x, L) and x.head:
                    if x.head in seen:
                        self.err(x.line, "input-twice", f"input {x.head} has a clause at line {seen[x.head]}; a union is one clause whose body is an OR")
                    seen.setdefault(x.head, x.line)
        self.declared[name] = ("comp", comp)
        self.side[name] = side

    def init_order(self, f: L, comp: str | None) -> None:
        """The key clause first, then the inputs that hold for every key;
        each group in the component's declared order."""
        cs = [c for c in f.items[3:] if isinstance(c, L)]
        keys = [i for i, c in enumerate(cs) if c.head == "key"]
        if keys and keys[0] != 0:
            self.err(cs[keys[0]].line, "init-order", f"{flat(f.items[1])}: the key clause stands before the inputs")
        for i in keys[1:]:
            self.err(cs[i].line, "init-order", f"{flat(f.items[1])}: a second key clause")
        if comp not in LIB.comps:
            return
        order = [r.name for r in LIB.relations(comp)[1] if r.is_input]
        groups = [[x for x in c.items[2:] if isinstance(x, L)] for c in cs if c.head == "key"]
        groups.append([c for c in cs if c.head != "key"])
        for g in groups:
            idx = [(order.index(x.head), x) for x in g if x.head in order]
            for (a, xa), (b, xb) in zip(idx, idx[1:]):
                if b < a:
                    self.err(xb.line, "init-order", f"{flat(f.items[1])}: input {xb.head} stands before {xa.head}, "
                             f"as {comp} declares them")

    def own_reads(self, f: L, name: str, comp: str | None) -> None:
        """Only Unfold's inputs read its instance's outputs: step, skip and
        take, with every site of such an atom joining, and no ALL over it."""
        cs = [c for c in f.items[3:] if isinstance(c, L)]
        inputs = [x for c in cs for x in (c.items[2:] if c.head == "key" else [c]) if isinstance(x, L)]
        for x in inputs:
            for a in walk(x):
                if not (isinstance(a, L) and a.head and a.head.startswith(name + ".")):
                    continue
                if comp != "Unfold" or x.head not in ("step", "skip", "take"):
                    self.err(a.line, "own-read", f"input {x.head} of {name} reads {a.head}: only Unfold's step, "
                             "skip and take read an output of their instance")
                elif any(isinstance(t, Sym) and t.text[:1] == "*" for t in leaves(a)):
                    self.err(a.line, "own-read", f"{a.head}: every site of an atom of an output joins in {x.head}")
            for u in walk(x):
                if isinstance(u, L) and u.head == "ALL" and f"({name}." in flat(u):
                    self.err(u.line, "own-read", f"an ALL inside input {x.head} reads an output of {name}")

    def choose(self, f: L, alt: bool) -> None:
        name = f.items[1].text
        ctx = Ctx(self, "RULE", alt, own=None, self_name=name)
        root = Scope(None)
        froms = 0
        cols: set[str] = set()
        keys: list[str] = []
        cand: set[str] = set()     # the labels from makes
        from_in_for: bool | None = None
        from_rel: list[str] = []   # the relation of from's first positive atom
        counts: list[tuple[L, bool]] = []   # each count clause, and whether it stands inside for
        nevers: list[L] = []
        parse_cs: list[L] = []

        def note_from(c: L, s: Scope, inside: bool) -> None:
            nonlocal from_in_for
            cand.update(s.made)
            from_in_for = inside
            first = next((x for x in c.items[1:] if isinstance(x, L) and x.head not in FORMS | OPS), None)
            if first is not None:
                from_rel.append(first.head)

        def inner(c: L, scope: Scope):
            nonlocal froms
            if c.head == "from":
                froms += 1
                ctx.made_anywhere = {k: 0 for k in root_labels(scope)}
                s = Scope(scope)
                ctx.body(c.items[1:], s)
                cols.update(s.made)
                note_from(c, s, True)
                ctx.require_keyed(c, scope)
            elif c.head == "never":
                self.err(c.line, "choose", "never stands after for")
            elif c.head == "ANY" and self.scene:
                count(c)
                counts.append((c, True))
            elif c.head == "count":
                self.err(c.line, "count", "(count any) is the mark (ANY)")
            else:
                self.err(c.line, "choose", f"unknown clause {c.head}")

        def count(c: L) -> None:
            if len(c.items) != 1:
                self.err(c.line, "choose", "(ANY) takes nothing")

        parses = 0
        for c in f.items[2:]:
            if not isinstance(c, L):
                continue
            if c.head == "for":
                ks = ctx.keyclause(c, root, inner)
                cols.update(ks)
                keys = list(ks)
            elif c.head == "from":
                froms += 1
                ctx.made_anywhere = {}
                s = Scope(root)
                ctx.body(c.items[1:], s)
                cols.update(s.made)
                note_from(c, s, False)
            elif c.head == "never":
                ctx.made_anywhere = {}
                ctx.body(c.items[1:], Scope(root))
                nevers.append(c)
            elif c.head == "ANY" and self.scene:
                count(c)
                counts.append((c, False))
            elif c.head == "count":
                self.err(c.line, "count", "(count any) is the mark (ANY)")
            elif c.head == "parse" and self.scene:
                parses += 1
                parse_cs.append(c)
            else:
                self.err(c.line, "choose", f"unknown clause {c.head}")
        for c, inside in counts:
            if from_in_for is not None and inside != from_in_for:
                self.err(c.line, "count-place", f"{name}: (ANY) stands beside its from, "
                         + ("inside for" if from_in_for else "after for"))
        for c in nevers:
            if from_rel:
                n = sum(1 for x in c.items[1:] if isinstance(x, L) and x.head == from_rel[0])
                if n < 2:
                    self.err(c.line, "never-reads", f"{name}: a never reads the candidate relation {from_rel[0]} "
                             f"twice, and this one reads it {n} times")
        if not self.scene and not nevers:
            self.err(f.line, "choose-no-never", f"{name}: a CHOOSE is written only for a pick with a never")
        self.choose_info[name] = (keys, cand)
        for c in parse_cs:
            self.parse_clause(c, alt, name)
        if self.scene:
            imp = self.imported
            if imp is not None and name in imp.chosen:
                self.err(f.line, "scene-pick", f"{name}: the arclog's CHOOSE and ONE picks are imported names, "
                         "and the file declares none of them")
            if parses > 1:
                self.err(f.line, "choose", f"{name}: {parses} parse clauses")
            rigid = getattr(self, "cur_rigid", None)
            shared = imp is not None and (name[1:] in imp.rigid_parts.get(rigid, ()) if rigid else name in imp.declared)
            if not parses and imp is not None and not shared:
                self.err(f.line, "scene-parse", f"{name}: a declaration with no parse carries the name of an "
                         + (f"arclog relation, and the arclog's {rigid} has no part of this name" if rigid else
                            "arclog relation, and the arclog file declares none of this name"))
            if parses and imp is not None and name in imp.declared and name in imp.concept_names:
                self.err(f.line, "scene-parse", f"{name}: the arclog file defines it, so it states no parse")
        if froms != 1:
            self.err(f.line, "choose", f"{froms} from clauses")
        elif not self.scene and one_states(f):
            self.err(f.line, "choose-one", f"{name}: every never says one candidate stands in two rows, so ONE marks state the pick")
        self.chosen.add(name)
        self.declare(name, cols, "RULE", f.line)

    def rigid(self, f: L, alt: bool) -> None:
        name = f.items[1].text
        ctx = Ctx(self, "DET", alt, own=None, self_name=name)
        root = Scope(None)

        names = self.rigid_parts.setdefault(name, {"pose"})
        pcols = self.part_cols.setdefault(name, {})
        self.rigid_keyed[name] = any(isinstance(c, L) and c.head == "key" for c in f.items[2:])
        inst_labels: set[str] = set()

        def part(p: L, s: Scope):
            if p.head and p.head.startswith("&"):
                names.add(p.head[1:])   # the program reads it as &<form>.<relation>
                labs = set(root_labels(s))
                inst_labels.update(labs)
                cs: set[str] = set()
                for t in p.items[1:]:
                    if isinstance(t, Sym) and t.text.lstrip("*^") not in labs:
                        cs.add(t.text.lstrip("*^"))
                    elif isinstance(t, L) and t.head and t.head.startswith(":"):
                        lab = [x.text.lstrip("*^") for x in t.items[1:] if isinstance(x, Sym)]
                        if not (lab and lab[0] in labs):
                            cs.add(t.head[1:])
                            cs.update(lab)
                pcols[p.head[1:]] = cs
            ctx.made_anywhere = {k: 0 for k in root_labels(s)}
            ctx.atom(p, Scope(s))

        def one_instance(cs) -> None:
            # a form, or a key, with no instance clause has one instance
            ins = [c for c in cs if isinstance(c, L) and c.head == "instance"]
            for c in ins[1:]:
                self.err(c.line, "rigid", "a second instance clause")

        one_instance(f.items[2:])
        for c in f.items[2:]:
            if isinstance(c, L) and c.head == "key":
                one_instance(c.items[2:])

        def parts(c: L, scope: Scope):
            if c.head == "instance":
                ctx.keyclause(c, scope, part)
            else:
                part(c, scope)

        for c in f.items[2:]:
            if not isinstance(c, L):
                continue
            if c.head == "key":
                ctx.keyclause(c, root, parts)
            elif c.head == "instance":
                ctx.keyclause(c, root, part)
            else:
                part(c, root)
        pcols["pose"] = inst_labels
        self.stored.update(f"{name}.{x}" for x in names)
        self.declared[name] = ("rigid", None)

    def out(self, f: L, alt: bool) -> None:
        """`(OUT <atom> [<atom>])`: the atoms of a key body, whose two `^` labels select the Position column and the
        Color column of the output (`docs/arclog/arclog.md#the-out-form`)."""
        atoms = f.items[1:]
        if not atoms or len(atoms) > 2 or not all(isinstance(a, L) and a.head and a.head not in FORMS | OPS for a in atoms):
            self.err(f.line, "key-form", "(OUT <atom> [<atom>]): one or two atoms")
            return
        scope = Scope(None, key_mode=True, kind="key")
        Ctx(self, "RULE", alt, own=None, self_name="").body(atoms, scope)
        if len(scope.keys) != 2:
            self.err(f.line, "key-form", f"OUT marks {len(scope.keys)} labels ^, and selects two columns")

    def parse_clause(self, c: L, alt: bool, name: str) -> None:
        """`(parse (<head sites>) <body>)`: a determination over the task
        side, whose head sites name the declaration's columns."""
        it = c.items
        if len(it) < 3 or not isinstance(it[1], L):
            self.err(c.line, "parse", "(parse (<head sites>) <body>)")
            return
        ctx = Ctx(self, "DET", alt, own=None, self_name=name)
        ctx.parse_mode = True
        top = Scope(None)
        for a in it[2:]:
            if isinstance(a, L) and a.head not in FORMS | OPS:
                for t in a.items[1:]:
                    for leaf in ([t] if isinstance(t, Sym) else leaves(t)):
                        if leaf.text[:1] == "*":
                            ctx.top_made.add(leaf.text[1:])
        ctx.body(it[2:], top)
        self.head_sites(it[1], top, "parse")
        # the head names the key's columns, then the candidate's; inside a
        # RIGID, (:Pose G) stands first
        head = list(it[1].items)
        if getattr(self, "cur_rigid", None):
            if not (head and isinstance(head[0], L) and head[0].head == ":Pose"):
                self.err(c.line, "parse-head", f"{name}: a parse inside a RIGID has (:Pose G) first in its head")
            else:
                head = head[1:]
        cols = [h.text if isinstance(h, Sym) else (h.head or "")[1:] for h in head]
        keys, cand = self.choose_info.get(name, ([], set()))
        if cols[:len(keys)] != keys:
            self.err(c.line, "parse-head", f"{name}: the head names the key's columns {' '.join(keys) or '(none)'} "
                     f"first, then the candidate's; it names {' '.join(cols)}")
        for x in cols[len(keys):]:
            if x not in cand:
                self.err(c.line, "parse-head", f"{name}: head column {x} is no label the from makes")

    def head_sites(self, head: L, scope: Scope, what: str) -> None:
        for s in head.items:
            toks = [s] if isinstance(s, Sym) else [t for t in s.items[1:]]
            for t in toks:
                for leaf in leaves(t):
                    if leaf.text[0] in "*^":
                        self.err(leaf.line, "head-site", f"{what} head site {leaf.text} carries a mark")
                    elif not (scope.visible(leaf.text) or leaf.text in scope.made):
                        self.err(leaf.line, "unbound", f"{what} head site {leaf.text}: no site of its body made it")

    def constraint_form(self, f: L, alt: bool) -> None:
        """A scene's top-level ALL: a constraint on the instance, its two
        lists checked as an ALL in a clause body is."""
        ctx = Ctx(self, "SCENE", alt, own=None, self_name="ALL")
        ctx.univ(f, Scope(None))

    def render(self, f: L, alt: bool) -> None:
        it = f.items
        if len(it) < 3 or not isinstance(it[1], Sym) or not isinstance(it[2], L):
            self.err(f.line, "render", "(RENDER <target> (<head sites>) <body>)")
            return
        target = it[1].text
        imp = self.imported
        tcols: set[str] | None = None
        if target in ("ex_input", "ex_output"):
            tcols = set(FACTS[target])
        elif imp is not None and (target in imp.stored or target in imp.params):
            base, _, out = target.partition(".")
            if out and base in imp.part_cols:
                pc = imp.part_cols[base].get(out)
                tcols = None if pc is None else set(pc) | {"Pose"}
            elif imp.cols.get(target):
                tcols = set(imp.cols[target])
        else:
            self.err(f.line, "render", f"{target}: a render's target is a task-side relation, ex_input or "
                     "ex_output, or a param")
        if tcols is not None:
            named = [h.text if isinstance(h, Sym) else (h.head or "")[1:] for h in it[2].items]
            if set(named) != tcols or len(named) != len(set(named)):
                self.err(f.line, "render-head", f"{target}: the head sites fall on the target's columns "
                         f"{' '.join(sorted(tcols))}; they name {' '.join(named)}")
        ctx = Ctx(self, "SCENE", alt, own=None, self_name="RENDER")
        top = Scope(None)
        for a in it[3:]:
            if isinstance(a, L) and a.head not in FORMS | OPS:
                for t in a.items[1:]:
                    for leaf in ([t] if isinstance(t, Sym) else leaves(t)):
                        if leaf.text[:1] == "*":
                            ctx.top_made.add(leaf.text[1:])
        ctx.body(it[3:], top)
        self.head_sites(it[2], top, "render")

    def rigid_group(self, f: L, alt: bool) -> None:
        """A scene's RIGID: its declarations and the relations derived from
        them, read as its parts with a :Pose column."""
        if len(f.items) < 2 or not isinstance(f.items[1], Sym):
            self.err(f.line, "rigid", "RIGID without a name")
            return
        name = f.items[1].text
        outer, self.cur_rigid = getattr(self, "cur_rigid", None), name
        self.forms(f.items[2:], alt)
        self.cur_rigid = outer
        parts = self.rigid_parts.setdefault(name, {"pose"})
        pcols = self.part_cols.setdefault(name, {})
        for x in f.items[2:]:
            if isinstance(x, L) and len(x.items) > 1 and isinstance(x.items[1], Sym) and x.items[1].text.startswith("&"):
                parts.add(x.items[1].text[1:])
                n = x.items[1].text
                pcols[n[1:]] = set(self.cols.get(n, set())) if x.head == "CHOOSE" else None
        self.declared[name] = ("rigid", None)

    def demonstrated(self, f: L, alt: bool) -> None:
        # an instance, on the side its input bodies read from: a determination
        # where they read the examples or a determination's Example column
        name = f.items[1].text
        inputs = [c for c in f.items[2:] if isinstance(c, L) and c.head != "DEMO_RULE"]
        side = "DET" if any(isinstance(a, L) and (a.head in ("ex_input", "ex_output") or (
            self.side.get(a.head) == "DET" and "E" in self.cols.get(a.head, ()) and e_site(a)))
            for c in inputs for a in walk(c)) else "RULE"
        ctx = Ctx(self, side, alt, own=None, self_name=name)
        root = Scope(None)
        keyed = False
        for c in f.items[2:]:
            if isinstance(c, L) and c.head == "DEMO_RULE":
                self.form(c, alt)
            elif isinstance(c, L) and c.head == "key":
                keyed = True
                ctx.keyclause(c, root, lambda inner, scope: ctx.input(inner, scope, "DemonstrationConsistency"))
            elif isinstance(c, L):
                ctx.input(c, root, "DemonstrationConsistency", broadcast=keyed)
        self.declared[name] = ("demo", keyed)
        self.side[name] = side


class Ctx:
    """One clause's checks."""

    def __init__(self, lt: Linter, side: str, alt: bool, own: str | None, self_name: str):
        self.lt, self.side, self.alt, self.own, self.self_name = lt, side, alt, own, self_name
        self.made_anywhere: dict[str, int] = {}
        # where a top-level (= *X 0) stands: an input, a clause, or neither
        self.zero_mode = ""
        self.top_zero: dict[str, int] = {}
        self.top_made: set[str] = set()   # the labels a top-level site of the clause makes
        self.parse_mode = False   # a scene declaration's parse: it reads the task side

    def err(self, line, code, msg):
        self.lt.err(line, code, msg)

    # ---- labels

    def fix(self, tok, new: str) -> None:
        if tok is None or tok.pos < 0 or tok.text == new:
            return
        col = tok.text.lstrip("*^")
        if tok.bare and new.lstrip("*^") != col:
            new = f"(:{col} {new})"
        self.lt.fixes[tok.pos] = (len(tok.text), new)

    def make(self, x: str, scope: Scope, line: int, mark: str, tok=None) -> None:
        if mark == "^" and not scope_key_mode(scope):
            self.err(line, "mark", f"^{x} outside a key body")
        x0 = scope.resolve(x)
        p = scope.pending_here(x0)
        if p is not None:
            self.err(line, "remade-export", f"{mark}{x} makes the label an earlier branch exports; name it")
            self.fix(tok, x0)
            p.named.add(x0)
            return
        if scope.visible(x0):
            self.err(line, "remade", f"{mark}{x} makes a label already in scope")
        elif x0 in self.made_anywhere:
            self.err(line, "label-clash", f"{mark}{x} reuses the name of another variable of the clause")
            n = 2
            while f"{x}{n}" in self.made_anywhere or re.search(rf"(?<![\w:&.]){x}{n}(?!\w)", self.lt.text):
                n += 1
            scope.alias[x] = f"{x}{n}"
            self.fix(tok, f"{mark}{x}{n}")
            x0 = f"{x}{n}"
        x = x0
        scope.made[x] = line
        self.made_anywhere[x] = line
        if mark == "^":
            ks = key_scope(scope)
            if ks is not None:
                ks.keys.append(x)

    def use(self, x: str, scope: Scope, line: int, tok=None) -> None:
        x0 = scope.resolve(x)
        if x0 != x:
            self.fix(tok, x0)
            x = x0
        p = scope.pending_here(x)
        if p is not None:
            p.named.add(x)
            return
        if not scope.visible(x) and x not in self.top_made:
            self.err(line, "unbound", f"{x} is used where no site made it")

    def label(self, t, scope: Scope, line: int, allow_fresh=True) -> str | None:
        if isinstance(t, Sym):
            s = t.text
            if s == "_":
                self.err(t.line, "wildcard", "no site uses _")
                return None
            if s == "0":
                return None
            if s[0] in "*^":
                if not allow_fresh:
                    self.err(t.line, "fresh-here", f"{s} where every site joins")
                self.make(s[1:], scope, t.line, s[0], t)
                return scope.resolve(s[1:])
            if re.fullmatch(r"[A-Z]\w*", s):
                self.use(s, scope, t.line, t)
                return scope.resolve(s)
            self.err(t.line, "label", f"{s} is no label")
        else:
            self.err(line, "label", "a list where a label stands")
        return None

    # ---- bodies

    def body(self, items, scope: Scope) -> None:
        self.whole_or = scope.kind == "top" and len(items) == 1 and isinstance(items[0], L) and items[0].head == "OR"
        for a in items:
            if isinstance(a, L):
                self.literal(a, scope)
            else:
                self.err(a.line, "body", f"{a.text} stands where an atom does")

    def literal(self, a: L, scope: Scope) -> None:
        h = a.head
        if h == "ONE":
            self.err(a.line, "one-place", "ONE stands at a clause's top level, after its body")
            return
        if h == "NOT":
            if len(a.items) != 2 or not isinstance(a.items[1], L) or a.items[1].head in FORMS | OPS:
                self.err(a.line, "not", "NOT takes one atom")
                return
            self.atom(a.items[1], scope, negated=True)
        elif h in OPS:
            self.constraint(a, scope)
        elif h == "OR":
            self.disj(a, scope)
        elif h == "IF":
            self.cond(a, scope)
        elif h == "ALL":
            self.univ(a, scope)
        else:
            self.atom(a, scope)

    def constraint(self, a: L, scope: Scope) -> None:
        if len(a.items) != 3:
            self.err(a.line, "constraint", "a constraint takes two labels")
            return
        x, y = a.items[1], a.items[2]
        if isinstance(x, Sym) and x.text == "0":
            self.err(a.line, "zero", "0 stands second in a constraint")
        if a.head == "=" and isinstance(y, Sym) and y.text[:1] == "*":
            self.err(a.line, "eq-order", f"(= {x.text if isinstance(x, Sym) else '...'} {y.text}): = makes its first label only")
            if isinstance(x, Sym) and x.text[:1] != "*":
                self.label(x, scope, a.line, allow_fresh=False)
            self.make(y.text[1:], scope, a.line, "*", y)
            scope.eq_made[scope.resolve(y.text[1:])] = a.line
            return
        if a.head == "=" and isinstance(x, Sym) and x.text[:1] == "*":
            v = x.text[1:]
            const = isinstance(y, Sym) and y.text == "0"
            if scope.pending_here(scope.resolve(v)) is not None:
                self.make(v, scope, a.line, "*", x)
                self.label(y, scope, a.line, allow_fresh=False)
                return
            if scope.kind not in ("first", "then"):
                if const and scope.kind == "top":
                    if self.zero_mode == "clause":
                        self.top_zero[scope.resolve(v)] = a.line
                    elif self.zero_mode != "input":
                        self.err(a.line, "head-zero", f"(= *{v} 0): {self.self_name} has one clause, "
                                 "so the column is 0 in every clause and is dropped")
                else:
                    where = {"top": "a body's top level", "later": "a later branch", "else": "an else",
                             "test": "an IF test", "all": "an ALL list", "key": "a key body"}[scope.kind]
                    self.err(a.line, "eq-make", f"(= *{v} ...) in {where}: = makes a label only in a first branch or a then")
            elif isinstance(y, Sym) and re.fullmatch(r"[A-Z]\w*", y.text) and scope.resolve(y.text) in scope.made_at:
                msg = f"(= *{v} {y.text}): {y.text} is made in this list, whose site could make {v}"
                if scope.union:
                    scope.eq_same[scope.resolve(v)] = (a.line, msg)   # a label the union exports passes
                else:
                    self.err(a.line, "eq-same-list", msg)
            self.label(y, scope, a.line, allow_fresh=False)
            self.make(v, scope, a.line, "*", x)
            scope.eq_made[scope.resolve(v)] = a.line
            return
        if a.head == "=" and isinstance(x, Sym) and re.fullmatch(r"[A-Z]\w*", x.text):
            v = scope.resolve(x.text)
            if scope.pending_here(v) is not None:
                pass
            elif v in scope.made:
                self.err(a.line, "eq-site", f"(= {v} ...): {v} is made at a site of this list, which could name the partner")
            elif not scope.visible(v):
                self.err(a.line, "eq-mark", f"(= {v} ...): = makes {v}, and a made label carries *")
                self.label(y, scope, a.line, allow_fresh=False)
                scope.made[v] = a.line
                self.made_anywhere[v] = a.line
                return
        for t in (x, y):
            self.label(t, scope, a.line, allow_fresh=False)

    def disj(self, a: L, scope: Scope) -> None:
        brs = a.items[1:]
        if len(brs) < 2 or not all(isinstance(b, L) for b in brs):
            self.err(a.line, "or", "OR holds two or more branches")
            return
        for i, j in implied_branches([b.items for b in brs]):
            self.err(brs[i].line, "or-implied", f"OR branch {i + 1} holds only where branch {j + 1} holds, "
                     "so it adds no rows")
        first = Scope(scope, kind="first", union=getattr(self, "whole_or", False))
        self.whole_or = False
        self.body(brs[0].items, first)
        exports = set(first.made)
        back = {v: k for k, v in first.alias.items()}
        for b in brs[1:]:
            s = Scope(scope, pending=set(first.made), alias=dict(first.alias), kind="later")
            self.body(b.items, s)
            exports &= s.named
        for x, (line, msg) in first.eq_same.items():
            if x not in exports:
                self.err(line, "eq-same-list", msg)
        for x, line in first.eq_made.items():
            if x not in exports:
                self.err(line, "eq-unexported", f"= makes {x}, and a later branch does not name it")
        for x in exports:
            scope.made[x] = first.made[x]
            if x in back:
                scope.alias[back[x]] = x
        if scope_key_mode(scope):
            ks = key_scope(scope)
            for x in list(ks.keys):
                if x in first.made and x not in exports:
                    self.err(a.line, "key-local", f"key column {x} is local to the first branch")

    def cond(self, a: L, scope: Scope) -> None:
        parts = a.items[1:]
        if len(parts) != 3 or not all(isinstance(p, L) for p in parts):
            self.err(a.line, "if", "IF holds a test, a then and an else")
            return
        test = Scope(scope, kind="test")
        self.body(parts[0].items, test)
        then = Scope(test, kind="then")
        self.body(parts[1].items, then)
        els = Scope(scope, pending=set(then.made), alias=dict(then.alias), kind="else")
        self.body(parts[2].items, els)
        for x, line in then.eq_made.items():
            if x not in els.named:
                self.err(line, "eq-unexported", f"= makes {x}, and the else does not name it")
        back = {v: k for k, v in then.alias.items()}
        for x in set(then.made) & els.named:
            scope.made[x] = then.made[x]
            if x in back:
                scope.alias[back[x]] = x

    def univ(self, a: L, scope: Scope) -> None:
        parts = a.items[1:]
        if len(parts) != 2 or not all(isinstance(p, L) for p in parts):
            self.err(a.line, "all", "ALL holds a domain and a body")
            return
        dom = Scope(scope, kind="all")
        self.body(parts[0].items, dom)
        self.body(parts[1].items, Scope(dom, kind="all"))

    # ---- atoms and sites

    def atom(self, a: L, scope: Scope, negated: bool = False) -> None:
        rel = a.head
        if rel is None:
            self.err(a.line, "atom", "an atom's head is a relation")
            return
        if rel in FORMS | OPS or rel.isupper():
            self.err(a.line, "atom", f"{rel} stands where an atom does")
            return
        fixed, tparam = self.columns(rel, a.line)
        missing = bare_read_columns(a, fixed, tparam)
        if missing:
            src = bare_read_source(self.lt.path.stem, self.self_name, rel) if not self.lt.scene else None
            self.err(a.line, "bare-read", f"{rel} is read with no site, and it has the columns {' '.join(missing)}"
                     + (f"; solver: {src}" if src else "; solver: not found"))
        # a site may hold 0 on a column of a number, a Box, a Position or an Offset
        for x in a.items[1:]:
            if isinstance(x, Sym) and x.text in ("*0", "^0"):
                self.err(x.line, "zero-site", f"{x.text}: 0 is a standing label, never made")
            if isinstance(x, L) and x.head and x.head.startswith(":") and len(x.items) == 2 \
                    and isinstance(x.items[1], Sym) and x.items[1].text == "0" and rel in LIB.top:
                t = dict((pascal(n), ty) for n, ty in LIB.top[rel]).get(x.head[1:])
                if t is not None and t not in ("number", "Box", "Position", "Offset"):
                    self.err(x.line, "zero-site", f"({x.head} 0): {rel}'s column {x.head[1:]} is a {t}, "
                             "which has no 0")
        if self.side == "RULE" and rel in ("ex_input", "ex_output"):
            self.err(a.line, "side", f"a RULE reads {rel}")
        if self.side == "DET" and rel == "input":
            self.err(a.line, "side", "a DET reads input")
        if self.side == "RULE" and not self.lt.scene and rel.startswith("&") and "." not in rel \
                and self.lt.side.get(rel) == "DET" and "E" in self.lt.cols.get(rel, ()) and e_site(a):
            # a RULE reads such a relation pooled, selecting no Example column
            self.err(a.line, "side", f"a RULE reads the Example column of {rel}; it reads it pooled, with no site on E")
        if self.lt.scene and rel in ("ex_input", "ex_output") and not self.parse_mode:
            self.err(a.line, "scene-task-side", f"{rel} read outside a parse: only a parse reads the task side")
        seen: set[str] = set()
        if not negated:
            for s in a.items[1:]:
                if isinstance(s, Sym) and s.text[:1] == "*":
                    scope.made_at.setdefault(s.text[1:], (a, s))
                elif isinstance(s, L) and len(s.items) == 2 and isinstance(s.items[1], Sym) \
                        and s.items[1].text[:1] == "*" and s.head and s.head[1:2].isupper():
                    scope.made_at.setdefault(s.items[1].text[1:], (a, s))
        for s in a.items[1:]:
            if isinstance(s, Sym):
                s.bare = True
                x = self.label(s, scope, a.line, allow_fresh=not negated)
                if x is not None:
                    self.col(s.text.lstrip("*^"), fixed, tparam, rel, s.line, seen, bare=True)
            elif isinstance(s, L):
                self.site(s, scope, fixed, tparam, rel, seen, negated)
            else:
                self.err(a.line, "site", "a string stands as a site")

    def site(self, s: L, scope, fixed, tparam, rel, seen, negated) -> None:
        h = s.head
        if not h or not h.startswith(":"):
            self.err(s.line, "site", f"a site's head is a :column, not {h}")
            return
        col = h[1:]
        self.col(col, fixed, tparam, rel, s.line, seen, bare=False)
        args = s.items[1:]
        if not args:
            self.err(s.line, "site", f"{h} takes a label")
        is_tparam = col[:1].islower()
        if not is_tparam and len(args) != 1:
            self.err(s.line, "site", f"fixed-type column {h} takes one label")
        for t in args:
            if isinstance(t, L):
                ph = t.head
                if not (ph and ph.startswith(":") and len(t.items) == 2):
                    self.err(t.line, "site", "a tuple position is (:position label)")
                    continue
                if not re.fullmatch(r"[A-Z]\w*", ph[1:]):
                    self.err(t.line, "field-case", f"({ph} ...): a record's field name is PascalCase")
                x = self.label(t.items[1], scope, t.line, allow_fresh=not negated)
                if x is not None and x == ph[1:]:
                    self.err(t.line, "elide", f"({ph} {t.items[1].text}) elides to {t.items[1].text}")
            else:
                if is_tparam and (len(args) > 1 or col == "key"):
                    t.bare = True   # a record's field elided to its label; a key is a record of one label as well
                x = self.label(t, scope, s.line, allow_fresh=not negated)
                if not is_tparam and len(args) == 1 and x == col:
                    self.err(s.line, "elide", f"({h} {t.text}) elides to {t.text}")

    def col(self, c, fixed, tparam, rel, line, seen, bare) -> None:
        if c in seen:
            self.err(line, "site-twice", f"two sites on column {c} of {rel}")
        seen.add(c)
        if fixed is None:
            return
        if c[:1].islower():
            if c not in tparam:
                self.err(line, "column", f"{rel} has no type-parameter column {c}")
        elif c not in fixed:
            if bare:
                self.err(line, "column", f"bare label {c}: {rel} has no column {c}")
            else:
                self.err(line, "column", f"{rel} has no column {c}")

    def columns(self, rel: str, line: int):
        """The relation's fixed and type-parameter columns; None where they
        are not known."""
        lt = self.lt
        if lt.scene and rel in SCENE_BUILTINS:
            return set(SCENE_BUILTINS[rel]), set()
        lc = lib_cols(rel)
        if lc is not None:
            return lc, set()
        if not rel.startswith("&"):
            self.err(line, "relation", f"unknown relation {rel}")
            return None, None
        base, _, out = rel.partition(".")
        if base == self.self_name and not out:
            self.err(line, "recursion", f"{rel} reads itself")
            return None, None
        # a scene reads the arclog's relations under their names, lifted
        # over the examples: a parse reads them first, the rest of the file
        # reads its own first
        lifted = False
        if lt.scene:
            imp = lt.imported
            own = base in lt.declared or base == self.own or (base in lt.all_names and not self.parse_mode)
            if imp is not None and base in imp.declared and (self.parse_mode or not own):
                lt, lifted = imp, True
        if base not in lt.declared and base != self.own:
            if base in lt.all_names:
                if not self.alt and base not in lt.concept_names:
                    self.err(line, "concept-empty", f"{base}: the concept reads a relation that only alts derive")
                elif not self.alt:
                    self.err(line, "order", f"{base} is read before its declaration")
            else:
                self.err(line, "undeclared", f"{base} is declared nowhere")
            return None, None
        if out and base in lt.rigid_parts:
            if out not in lt.rigid_parts[base]:
                self.err(line, "rigid-part", f"{rel}: no atom of the RIGID_DET {base} names {out}; its parts are "
                         + " ".join(sorted(lt.rigid_parts[base] - {"pose"})))
                return None, None
            pc = lt.part_cols.get(base, {}).get(out)
            if pc is None:
                return None, None
            return set(pc) | {"Pose"}, ({"key"} if lt.rigid_keyed.get(base) else set())
        if out:
            comp = lt.inst_comp.get(base)
            if comp is None:
                return None, None
            cc = comp_cols(comp, out)
            if cc is None:
                self.err(line, "relation", f"{comp} has no relation {out}")
                return None, None
            if (lifted or not self.lt.scene) and (lifted or self.side in ("DET", "ANY")) \
                    and lt.side.get(base) != "DET":
                return cc[0] | {"E"}, cc[1]
            return cc
        d = lt.declared.get(base)
        if isinstance(d, tuple) and d[0] == "demo" and not out:
            return set(), {"o", "i", "v"} | ({"key"} if d[1] else set())
        if base in lt.inst_comp:
            self.err(line, "relation", f"{base} is an instance: read one of its relations")
            return None, None
        cols = set(lt.cols.get(base, set()))
        # in a combination's block, an alt of the combination that a later
        # ALTS form gives rederives the relation with its own columns
        if lt.alt_chain and lt.pre is not None:
            chain = set(lt.alt_chain)
            for (alts, name), cs in lt.pre.chain_cols.items():
                if name == base and alts <= chain:
                    cols |= cs
        if not cols:
            return None, None
        if (lifted or not self.lt.scene) and (lifted or self.side in ("DET", "ANY")) \
                and lt.side.get(base) == "RULE":
            cols.add("E")
        return cols, set()

    # ---- key clauses

    def keyclause(self, c: L, root: Scope, inner) -> list[str]:
        """`(key (<body>) <inner>...)`: the body's ^ labels are the key's
        columns, in scope in the clauses inside."""
        it = c.items
        if len(it) < 2 or not isinstance(it[1], L) or not all(isinstance(x, L) for x in it[1].items):
            self.err(c.line, "key-form", f"({c.head} (<body>) ...): the body is one list of atoms")
            return []
        ks = Scope(root, key_mode=True, kind="key")
        self.body(it[1].items, ks)
        if not ks.keys:
            self.err(c.line, "key-form", f"{c.head} body marks no label ^")
        scope = Scope(root)
        for k in ks.keys:
            if k in ks.made:
                scope.made[k] = ks.made[k]
        self._keys = set(ks.keys)
        for x in it[2:]:
            if isinstance(x, L):
                inner(x, scope)
                self.require_keyed(x, scope)
        return ks.keys

    def require_keyed(self, x: L, scope: Scope) -> None:
        if x.head == "ANY":
            return
        text = flat(x)
        keys = set(scope.made)
        if not (keys & set(re.findall(r"(?<![\w*^:&.])([A-Z]\w*)", text))) and \
                not (self.own and f"{self.own}." in text):
            self.err(x.line, "broadcast-inside", f"({x.head} ...) reads no key label and stands inside the key")

    # ---- instance inputs

    def input(self, c: L, root: Scope, comp: str | None, broadcast: bool = False) -> None:
        it = c.items
        if len(it) < 2 or not isinstance(it[1], L):
            self.err(c.line, "input", f"({c.head} (<head sites>) <body>)")
            return
        name = c.head
        if comp in LIB.comps:
            _, rels = LIB.relations(comp)
            r = next((r for r in rels if r.name == name), None)
            if r is None or not r.is_input:
                self.err(c.line, "input", f"{comp} has no input {name}")
        scope = Scope(root)
        self.made_anywhere = {k: 0 for k in root_labels(root)}
        outer, self.zero_mode = self.zero_mode, "input"
        self.body(it[2:], scope)
        self.zero_mode = outer
        for s in it[1].items:
            toks = [s] if isinstance(s, Sym) else [t for t in s.items[1:]]
            for t in toks:
                for leaf in leaves(t):
                    if leaf.text[0] in "*^":
                        self.err(leaf.line, "head-site", f"head site {leaf.text} carries a mark")
                    elif leaf.text == "0":
                        self.err(leaf.line, "head-zero", f"({c.head} ...): a head site holds 0; the site holds a label "
                                 "that the body makes with (= *X 0)")
                    elif not scope.visible(leaf.text):
                        self.err(leaf.line, "unbound", f"head site {leaf.text}: no site made it")


def bare_read_columns(a: L, fixed: set[str] | None, tparam: set[str] | None) -> list[str]:
    """The columns of a relation that an atom with no site reads, sorted; none where the atom has a site or the
    relation has no column. The column E, which a read of a relation over the examples adds, is no column here."""
    if len(a.items) > 1:
        return []
    return sorted(((fixed or set()) - {"E"}) | (tparam or set()))


def or_start(f: L) -> int:
    """Where a DET_OR_RULE or RULE_OR_DET line's proposers start: after its
    name, and after its gloss where it has one."""
    return 3 if len(f.items) > 2 and isinstance(f.items[2], Str) else 2


def site_labels(a: L) -> dict[str, str] | None:
    """An atom's labels by column, a type-parameter column's by position;
    None where a site is no label."""
    out: dict[str, str] = {}
    for s in a.items[1:]:
        if isinstance(s, Sym):
            out[s.text.lstrip("*^")] = s.text.lstrip("*^")
            continue
        if not (isinstance(s, L) and s.head and s.head.startswith(":")):
            return None
        col = s.head[1:]
        for t in s.items[1:]:
            if isinstance(t, Sym):
                k = f"{col}.{t.text.lstrip('*^')}" if col[:1].islower() else col
                out[k] = t.text.lstrip("*^")
            elif isinstance(t, L) and t.head and t.head.startswith(":") and len(t.items) == 2 \
                    and isinstance(t.items[1], Sym):
                out[f"{col}.{t.head[1:]}"] = t.items[1].text.lstrip("*^")
            else:
                return None
    return out


def norm(x) -> str:
    """A form's text with the marks that make a label dropped."""
    return re.sub(r"(?<![\w])[*^]", "", flat(x))


def implies(bi: list, bj: list) -> bool:
    """Branch bi holds only where branch bj holds: each positive atom of bj
    is an atom of bi on the same relation that reads a subset of its sites,
    and each other item of bj stands in bi as written. bj's labels then
    take the values bi gives them."""
    if not bj:
        return False
    texts = {norm(x) for x in bi}
    for y in bj:
        if not isinstance(y, L):
            return False
        if y.head not in FORMS | OPS | {"ONE"}:
            sy = {norm(t) for t in y.items[1:]}
            if not any(isinstance(x, L) and x.head == y.head and sy <= {norm(t) for t in x.items[1:]} for x in bi):
                return False
        elif norm(y) not in texts:
            return False
    return True


def implied_branches(branches: list[list]) -> list[tuple[int, int]]:
    """Each branch of an `OR` that holds only where another branch holds (`implies`), by index, with the branch it
    holds only where, in order of the branches: of two branches that hold only where each other holds, the later is
    implied, and a branch already implied is no implying branch."""
    out: list[tuple[int, int]] = []
    gone: set[int] = set()
    for i, bi in enumerate(branches):
        j = next((j for j, bj in enumerate(branches) if j != i and j not in gone and implies(bi, bj)
                  and not (implies(bj, bi) and j > i)), None)
        if j is not None:
            out.append((i, j))
            gone.add(i)
    return out


def one_states(f: L) -> bool:
    """A CHOOSE whose every never is two atoms of the candidate relation
    that agree on some of the pick's columns, with the rest different: a
    pick that ONE marks state."""
    froms = [x for c in f.items[2:] if isinstance(c, L) and c.head in ("for", "from")
             for x in ([c] if c.head == "from" else c.items[2:]) if isinstance(x, L) and x.head == "from"]
    if len(froms) != 1 or len(froms[0].items) != 2 or not isinstance(froms[0].items[1], L):
        return False
    cand = froms[0].items[1]
    cols = site_labels(cand)
    if cols is None:
        return False

    def ne(x):
        if isinstance(x, L) and x.head == "!=" and len(x.items) == 3 and all(isinstance(y, Sym) for y in x.items[1:]):
            return frozenset(y.text for y in x.items[1:])
        return None
    for c in f.items[2:]:
        if not (isinstance(c, L) and c.head == "never"):
            continue
        atoms = [x for x in c.items[1:] if isinstance(x, L) and x.head == cand.head]
        rest = [x for x in c.items[1:] if not (isinstance(x, L) and x.head == cand.head)]
        if len(atoms) != 2:
            return False
        l1, l2 = site_labels(atoms[0]), site_labels(atoms[1])
        if l1 is None or l2 is None or set(l1) != set(cols) or set(l2) != set(cols):
            return False
        differ = {frozenset((l1[k], l2[k])) for k in cols if l1[k] != l2[k]}
        groups = []
        for x in rest:
            if ne(x) is not None:
                groups.append({ne(x)})
            elif isinstance(x, L) and x.head == "OR" and all(
                    isinstance(b, L) and len(b.items) == 1 and ne(b.items[0]) is not None for b in x.items[1:]):
                groups.append({ne(b.items[0]) for b in x.items[1:]})
            else:
                return False
        if len(groups) != 1 or groups[0] != differ:
            return False
    return True


def e_site(a: L) -> bool:
    """Whether the atom has a site on the Example column E."""
    return any((isinstance(x, Sym) and x.text.lstrip("*") == "E") or (isinstance(x, L) and x.head == ":E")
               for x in a.items[1:])


def root_labels(s: Scope) -> list[str]:
    out = []
    while s:
        out += list(s.made)
        s = s.parent
    return out


def scope_key_mode(s: Scope) -> bool:
    while s:
        if s.key_mode:
            return True
        s = s.parent
    return False


def key_scope(s: Scope) -> Scope | None:
    while s:
        if s.key_mode:
            return s
        s = s.parent
    return None


# ---------------------------------------------------------------- structure

SLUG = r"[a-z0-9]+(-[a-z0-9]+)*"


def output_forms(lt: Linter, forms, pl: list[Placed]) -> None:
    """The checks of the `OUT` forms of an arclog file (`docs/arclog/arclog.md#the-out-form`): the tail holds one, a
    block holds at most one, each stands under no claim block, in the tail after every other form and in an `ALT`
    block after each form other than its `ALT` blocks and `ALTS` forms, and none restates the `OUT` form its cases
    take without it (`restated_outs`)."""
    err = lt.err
    for p in pl:
        if p.form.head == "OUT" and p.slug is not None:
            err(p.form.line, "output-place", "an OUT form stands under no claim block")
    blocks = [(forms, False), *((block.items[2:], True) for _, block in alt_blocks(forms))]
    for items, in_alt in blocks:
        outs = [i for i, f in enumerate(items) if isinstance(f, L) and f.head == "OUT"]
        if not in_alt and not outs:
            err(0, "no-output", "no OUT form in the tail")
        for i in outs[1:]:
            err(items[i].line, "no-output", "a second OUT form in its block")
        for i in outs:
            if any(isinstance(g, L) and not (in_alt and g.head in ("ALT", "ALTS")) for g in items[i + 1:]):
                err(items[i].line, "output-place", "an OUT form stands after every other form of its block"
                    + (", other than its ALT blocks and ALTS forms" if in_alt else ""))
    for p in restated_outs(pl):
        err(p.form.line, "output-restated", "an OUT form equal to the OUT form its cases take without it: the block "
            "holds no such form")


def structure(lt: Linter, forms) -> None:
    """The checks over the file's layout: the order of its top-level forms,
    its claim blocks, where each form stands, and the names it spells."""
    err = lt.err
    pl = placements(forms)
    lt.placed = pl
    imp = lt.imported
    what = "scene" if lt.scene else "arclog"

    # -- the top level
    seen_other = seen_tail = seen_render = False
    for f in forms:
        if not isinstance(f, L):
            continue
        if f.head in CLAIMS:
            if seen_other:
                err(f.line, "top-order", f"claim {flat(f.items[1]) if len(f.items) > 1 else ''} stands after a form "
                    "that is no claim block: the claim blocks come first")
        elif f.head == "ALTS":
            seen_other = True
            if seen_tail and not lt.scene and claims_of(forms):
                err(f.line, "top-order", "an ALTS form stands after the tail: the ALTS forms come before it")
        else:
            seen_other = True
            seen_tail = True
    for container in [forms] + [f.items[2:] for f in forms for f in walk(f) if isinstance(f, L) and f.head == "ALT"]:
        seen_render = False
        for f in container:
            if not isinstance(f, L) or not lt.scene:
                continue
            if f.head == "RENDER":
                seen_render = True
            elif seen_render and f.head not in ("ALTS", "ALT"):
                err(f.line, "render-place", "RENDER forms stand at the tail, after every other form")

    # -- a form that repeats another of its block
    def no_repeats(container) -> None:
        seen: dict[str, int] = {}
        for f in container:
            if not isinstance(f, L):
                continue
            text = flat(f)
            if text in seen:
                err(f.line, "repeat-form", f"{f.head} {flat(f.items[1]) if len(f.items) > 1 else ''} repeats the "
                    f"form at line {seen[text]} of its block")
            seen.setdefault(text, f.line)
            if f.head in CLAIMS or f.head in ("ALTS", "ALT"):
                no_repeats(f.items)
    no_repeats(forms)
    for kind, p, ref, shared in alt_repeats(pl):
        where = f"{p.form.head} {p.name} in {'/'.join(p.alts)} repeats the form at line {ref.form.line}"
        if kind == "enclosing":
            err(p.form.line, "repeat-form", f"{where}, which its case reads with the same meaning")
        else:
            err(p.form.line, "repeat-form", f"{where}, with the same meaning in each alt that reads it; one form "
                f"in {'/'.join(shared) or 'the concept'} states it")

    if not lt.scene:
        data = lt.path.with_suffix(".arcdata")
        excluded = []
        if data.exists():
            try:
                excluded = [frozenset(x.text for x in f.items[1].items if isinstance(x, Sym))
                            for f in read(read_file(data)) if isinstance(f, L) and f.head == "exclude"
                            and len(f.items) > 1 and isinstance(f.items[1], L)]
            except SyntaxError:
                pass
        for n, case, ps in unstated_combinations(pl, forms, excluded):
            where = " and ".join(f"{'/'.join(p.alts)} (line {p.form.line})" for p in ps)
            err(ps[-1].form.line, "alt-combination", f"{n}: {where} each rederive it, and no nested ALT states "
                f"what the combination {' & '.join(sorted(case))} derives")

    # -- claim blocks
    top_claims = claims_of(forms)
    slugs: dict[str, int] = {}
    for f in top_claims:
        it = f.items
        if len(it) < 2 or not isinstance(it[1], Sym):
            continue
        sl = it[1].text
        if not re.fullmatch(SLUG, sl):
            err(f.line, "spelling", f"claim slug {sl}: a slug is lowercase words joined by -")
        if sl in slugs:
            err(f.line, "claim", f"claim {sl} stands twice, at lines {slugs[sl]} and {f.line}")
        slugs.setdefault(sl, f.line)
        if lt.scene and len(it) > 2 and isinstance(it[2], Str):
            err(f.line, "scene-claim", f"claim {sl}: a scene's claim block has no text")
    concept = {f.items[1].text: f.head for f in top_claims if len(f.items) > 1 and isinstance(f.items[1], Sym)}
    for a in walk(L(list(forms), 0)):
        if not (isinstance(a, L) and a.head == "ALT"):
            continue
        for c in a.items[2:]:
            if not (isinstance(c, L) and c.head in CLAIMS and len(c.items) > 1 and isinstance(c.items[1], Sym)):
                continue
            sl = c.items[1].text
            if sl in concept and concept[sl] != c.head:
                # a block under a slug the concept has no claim of is a claim the alt adds
                err(c.line, "alt-claim", f"{c.head} {sl} in {flat(a.items[1])}: an ALT's block on a concept's "
                    f"claim is of the same kind")
            if lt.scene and len(c.items) > 2 and isinstance(c.items[2], Str):
                err(c.line, "scene-claim", f"claim {sl}: a scene's claim block has no text")
            if not lt.scene and not (len(c.items) > 2 and isinstance(c.items[2], Str)):
                err(c.line, "claim-text", f"claim {sl} in {flat(a.items[1])}: an ALT's block holds the alt's "
                    "reading of the claim as its text")
    if lt.scene and imp is not None:
        imp_forms = read(imp.text)
        order = [f.items[1].text for f in claims_of(imp_forms) if len(f.items) > 1 and isinstance(f.items[1], Sym)]
        kinds = {f.items[1].text: f.head for f in claims_of(imp_forms) if len(f.items) > 1}
        last = -1
        for f in top_claims:
            sl = f.items[1].text if len(f.items) > 1 and isinstance(f.items[1], Sym) else None
            if sl is None or sl not in kinds or kinds[sl] != f.head:
                err(f.line, "scene-claim", f"{f.head} {sl}: the arclog file has no {f.head} claim of this slug")
                continue
            if order.index(sl) < last:
                err(f.line, "scene-claim", f"claim {sl}: the blocks follow the arclog's claim order")
            last = max(last, order.index(sl))
        if not order and top_claims:
            err(top_claims[0].line, "scene-claim", "the arclog file has no claims, so the forms stand at the top level")
        # the ALTS forms are the arclog's
        amap = alts_map(imp_forms)
        for f in forms:
            if isinstance(f, L) and f.head == "ALTS" and len(f.items) > 1 and isinstance(f.items[1], Sym):
                nm = f.items[1].text
                if nm not in amap:
                    err(f.line, "scene-alts", f"{nm}: the arclog file has no ALTS form of this name")
                    continue
                for a in walk(f):
                    if isinstance(a, L) and a.head == "ALT" and len(a.items) > 1 and isinstance(a.items[1], Sym) \
                            and a.items[1].text not in set().union(*amap.values()):
                        err(a.line, "scene-alts", f"{a.items[1].text}: the arclog file has no ALT of this name")

    # -- the forms a scene does not use
    if lt.scene:
        for p in pl:
            if p.form.head in ("DET", "DET_OR_RULE", "RULE_OR_DET", "RIGID_DET", "APPROXIMATED"):
                err(p.form.line, "scene-form", f"{p.form.head}: a scene derives with RULE, declares with CHOOSE "
                    "and groups with RIGID")
            if p.form.head == "RENDER" and p.slug is not None:
                err(p.form.line, "render-place", "a RENDER stands at the tail, under no claim block")

    # -- APPROXIMATED and OUT
    for f in forms:
        for c in walk(f):
            if not (isinstance(c, L) and c.head in CLAIMS):
                continue
            subs = [x for x in c.items[2:] if isinstance(x, L)]
            for i, x in enumerate(subs):
                if x.head == "APPROXIMATED" and (c.head != "OUTPUT" or i != 0):
                    err(x.line, "approximated", "an APPROXIMATED form stands first in an OUTPUT block, after its text")
                if x.head == "APPROXIMATED" and not (len(x.items) == 2 and isinstance(x.items[1], Str)):
                    err(x.line, "approximated", "(APPROXIMATED \"<the rule the program runs>\")")
    if not lt.scene:
        output_forms(lt, forms, pl)

    # -- where a relation stands
    concept_pl = [p for p in pl if not p.alts]
    tail = {p.name for p in concept_pl if p.slug is None and p.name}
    if not lt.scene and top_claims:
        texts = {f.items[1].text: f.items[2].text for f in top_claims
                 if len(f.items) > 2 and isinstance(f.items[1], Sym) and isinstance(f.items[2], Str)}
        named = {sl: set(re.findall(r"&\w+", t)) for sl, t in texts.items()}
        block_reads: dict[str, set[str]] = defaultdict(set)
        for p in concept_pl:
            if p.slug is not None:
                block_reads[p.slug] |= reads(p.form, p.name)
        order = [f.items[1].text for f in top_claims if len(f.items) > 1 and isinstance(f.items[1], Sym)]
        for p in concept_pl:
            if not p.name or p.slug is None or p.rigid:
                continue
            namers = [sl for sl in order if p.name in named.get(sl, ())]
            first = next((sl for sl in order if p.name in block_reads[sl]), None)
            if namers and first is not None and order.index(first) < order.index(namers[0]):
                namers = [first]   # an earlier claim reads it: it stands under that claim
            if namers:
                if p.slug != namers[0]:
                    err(p.form.line, "stands-under", f"{p.name} stands under {p.slug}; a parameter stands under the "
                        f"claim whose text names it, {namers[0]}")
                continue
            first = next((sl for sl in order if p.name in block_reads[sl]), None)
            if first is not None and first != p.slug and order.index(first) > order.index(p.slug):
                err(p.form.line, "stands-under", f"{p.name} stands under {p.slug}, and the first claim that reads it "
                    f"is {first}")

    # -- an ALT's forms: outside its claim blocks, a form derives a relation of the concept's tail, or one that an OUT
    # form of the block, or of a block that holds it, reads: that form is the output of the block's cases
    if top_claims:
        for path, a in alt_blocks(forms):
            output_reads = {r for o in pl if o.form.head == "OUT" and set(o.alts) <= set(path) for r in reads(o.form)}
            for x in a.items[2:]:
                if not isinstance(x, L) or x.head in CLAIMS | {"ALT", "ALTS", "RENDER", "ALL", "OUT"}:
                    continue
                nm = x.items[1].text if len(x.items) > 1 and isinstance(x.items[1], Sym) else None
                if nm not in tail and nm not in output_reads:
                    err(x.line, "alt-tail", f"{nm} stands in {flat(a.items[1])} outside a claim block, so it is a "
                        "tail form the alt rederives or the relation an OUT form of its block reads, and the "
                        "concept's tail has none of this name")

    # -- a relation under NOT is derived in every case that reads it
    derived: dict[tuple, set[str]] = defaultdict(set)
    for p in pl:
        if p.name:
            derived[p.alts].add(p.name)
            if p.rigid:
                derived[p.alts].add(p.rigid)
    base_names = derived[()] | (imp.concept_names if imp is not None else set())
    for p in pl:
        if not p.alts:
            continue
        # every block whose alts the case holds derives for it
        have = set(base_names).union(*(ns for q, ns in derived.items() if set(q) <= set(p.alts)))
        for n in walk(p.form):
            if isinstance(n, L) and n.head == "NOT" and len(n.items) == 2 and isinstance(n.items[1], L):
                h = n.items[1].head or ""
                b = h.partition(".")[0]
                if h.startswith("&") and b not in have and b in lt.all_names:
                    err(n.line, "not-undefined", f"(NOT ({h} ...)) in {'/'.join(p.alts)}: a relation under NOT is "
                        "derived in every case that reads it, and no block of this case derives it")

    # -- the scene's shared names and rederivations
    if lt.scene and imp is not None:
        imp_slug = {p.name: p.slug for p in imp.placed if p.name and not p.alts}
        for p in pl:
            if not p.name or p.form.head == "RENDER":
                continue
            nm = p.name
            if p.rigid is None and nm in imp.declared and not p.alts:
                mine, theirs = lt.declared.get(nm), imp.declared.get(nm)
                inst_m = isinstance(mine, tuple) and mine[0] == "comp"
                inst_t = isinstance(theirs, tuple) and theirs[0] == "comp"
                if inst_m != inst_t:
                    err(p.form.line, "shared-cols", f"{nm}: the arclog's {nm} is "
                        + ("an instance" if inst_t else "a relation") + " and this one is "
                        + ("an instance" if inst_m else "a relation") + "; two definitions share a name only where "
                        "they have the same columns")
                elif not inst_m and lt.decl_cols.get(nm) and imp.decl_cols.get(nm) and imp.cols.get(nm):
                    a, b = lt.decl_cols[nm][0], imp.decl_cols[nm][0]
                    if a != b and not (imp.side.get(nm) == "RULE" and a == b | {"E"}):
                        err(p.form.line, "shared-cols", f"{nm}: columns {' '.join(sorted(a))} here and "
                            f"{' '.join(sorted(b))} in the arclog; two definitions share a name only where they have "
                            "the same columns")
                if p.form.head == "CHOOSE" and imp_slug.get(nm) is not None and p.slug != imp_slug[nm]:
                    err(p.form.line, "scene-block", f"{nm} stands under {p.slug}, and the arclog declares it "
                        f"under {imp_slug[nm]}")
            if p.rigid is not None and p.rigid in imp.part_cols and nm[1:] in imp.part_cols[p.rigid]:
                a = lt.part_cols.get(p.rigid, {}).get(nm[1:])
                b = imp.part_cols[p.rigid][nm[1:]]
                if a is not None and b is not None and a != b:
                    err(p.form.line, "shared-cols", f"{p.rigid}.{nm[1:]}: columns {' '.join(sorted(a))} here and "
                        f"{' '.join(sorted(b))} in the arclog's RIGID_DET; a part that both name has the same columns")
        concept_forms = {p.name: p.form for p in pl if p.name and not p.alts}
        for p in pl:
            if not (p.name and p.alts and p.name in concept_forms):
                continue
            if flat(p.form) == flat(concept_forms[p.name]):
                err(p.form.line, "alt-same", f"{p.name} in {'/'.join(p.alts)} is the concept's form as written: an "
                    "ALT holds only forms its alt rederives or adds")
            cs = lt.decl_cols.get(p.name, [])
            if len(cs) > 1 and p.form.head == "CHOOSE" and concept_forms[p.name].head == "RULE" \
                    and cs[0] != cs[-1]:
                err(p.form.line, "alt-cols", f"{p.name}: an ALT rederives a relation with the same name and columns, "
                    f"{' '.join(sorted(cs[0]))}")

    # -- spelling
    for f in forms:
        for a in walk(f):
            if not isinstance(a, L) or len(a.items) < 2:
                continue
            x = a.items[1]
            if a.head == "ALTS" and isinstance(x, Sym) and not re.fullmatch(r"\$[a-z][a-z0-9_]*", x.text):
                err(a.line, "spelling", f"ALTS {x.text}: an ALTS form's name is $ and a lowercase word")
            if a.head in ("ALT", "DEMO_RULE"):
                n = x.text if isinstance(x, Sym) else (x.head if isinstance(x, L) else None)
                if n is not None and not re.fullmatch(r"\$[A-Z][A-Za-z0-9]*", n):
                    err(a.line, "spelling", f"{a.head} {n}: an alt's name is $ and a PascalCase word")
            # a RULE_OR_DET line on an instance's output names the output as it is read
            out_line = a.head == "RULE_OR_DET" and isinstance(x, Sym) and \
                re.fullmatch(r"&[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*", x.text) is not None
            if a.head in DECL_HEADS and isinstance(x, Sym) and x.text.startswith("&") and not out_line \
                    and not re.fullmatch(r"&[a-z][a-z0-9_]*", x.text):
                err(a.line, "spelling", f"{a.head} {x.text}: a declared name is & and a snake_case word")

    # -- demonstrated rules
    for f in forms:
        for d in walk(f):
            if not (isinstance(d, L) and d.head == "DEMONSTRATED"):
                continue
            vals = [c for c in d.items[2:] if isinstance(c, L) and c.head == "value"]
            for c in d.items[2:]:
                if isinstance(c, L) and c.head == "key":
                    vals += [x for x in c.items[2:] if isinstance(x, L) and x.head == "value"]
            vlabs: set[str] = set()
            for v in vals[:1]:
                if len(v.items) > 1 and isinstance(v.items[1], L):
                    vlabs = {t.text for h in v.items[1].items for t in leaves(h) if isinstance(t, Sym)} | \
                            {h.text for h in v.items[1].items if isinstance(h, Sym)}
            for r in d.items[2:]:
                if not (isinstance(r, L) and r.head == "DEMO_RULE"):
                    continue
                it = r.items
                if len(it) > 1 and isinstance(it[1], L):
                    if len(it[1].items) < 2:
                        err(r.line, "demo-rule", f"{flat(it[1])}: a rule with no field is named by its bare name")
                    for t in it[1].items[1:]:
                        if not (isinstance(t, Sym) and t.text[:1] == "*"):
                            err(r.line, "demo-rule", f"{flat(it[1])}: a rule names each field with a fresh label")
                if len(it) < 2 or not (isinstance(it[1], L) or (isinstance(it[1], Sym) and it[1].text[:1] == "$")):
                    err(r.line, "demo-rule", "(DEMO_RULE $Name [\"<the rule's text>\"] <clauses>)")
                preds = [x for x in walk(r) if isinstance(x, L) and x.head in ("RULE", "DET") and len(x.items) > 1
                         and isinstance(x.items[1], Sym) and x.items[1].text == "&prediction"]
                if not preds:
                    err(r.line, "demo-rule", f"{flat(it[1]) if len(it) > 1 else ''}: a demonstrated rule derives "
                        "&prediction")
                for pr in preds:
                    labs = {t.text.lstrip("*^") for t in walk(pr) if isinstance(t, Sym)}
                    miss = vlabs - labs
                    if miss:
                        err(pr.line, "demo-rule", f"&prediction has the columns the value head names; it lacks "
                            f"{' '.join(sorted(miss))}")


UNFOLD_OWN = {"step", "skip", "take"}


def form_reads(f: L, name: str | None) -> set[str]:
    """The relations a form reads, by base name: a read of an instance's
    output is a read of the instance, and what an instance's inputs read
    the instance reads. An Unfold instance's step, skip and take reading its
    own outputs are no reads."""
    if f.head == "INIT" and name is not None and len(f.items) > 2 and isinstance(f.items[2], Sym) \
            and f.items[2].text == "Unfold":
        cs = [c for c in f.items[3:] if isinstance(c, L)]
        parts = [(c.items[1] if len(c.items) > 1 else None, False) for c in cs if c.head == "key"]
        parts += [(x, x.head in UNFOLD_OWN) for c in cs
                  for x in (c.items[2:] if c.head == "key" else [c]) if isinstance(x, L)]
        out = set()
        for x, own_ok in parts:
            for a in walk(x):
                if isinstance(a, L) and a.head and a.head.startswith("&"):
                    b = a.head.partition(".")[0]
                    if not (own_ok and b == name):
                        out.add(b)
        return out
    return {a.head.partition(".")[0] for a in walk(f)
            if isinstance(a, L) and a.head and a.head.startswith("&") and a is not f}


def cycles(lt: Linter, pl: list[Placed]) -> None:
    """An arclog program is a DAG of relations: no relation reads itself
    through reads, on the concept program and on each alt path, where an
    alt's forms of a name stand for the concept's."""
    paths = sorted({p.alts for p in pl}, key=lambda a: (len(a), a))
    seen: set[frozenset[str]] = set()
    for path in paths:
        best: dict[str, tuple] = {}   # each name's deepest block on the path
        for p in pl:
            if p.name and set(p.alts) <= set(path) and len(p.alts) >= len(best.get(p.name, ())):
                best[p.name] = p.alts
        graph: dict[str, set[str]] = defaultdict(set)
        line: dict[str, int] = {}
        for p in pl:
            if p.name and p.alts == best.get(p.name) and set(p.alts) <= set(path):
                graph[p.name] |= form_reads(p.form, p.name)
                line.setdefault(p.name, p.form.line)
                if p.rigid:
                    graph[p.rigid] |= form_reads(p.form, p.name)
        nodes = [n for n in graph]
        for n in nodes:
            graph[n] &= set(graph)
        # strongly connected components (Tarjan)
        index: dict[str, int] = {}
        low: dict[str, int] = {}
        stack: list[str] = []
        on: set[str] = set()
        comps: list[list[str]] = []

        def visit(v: str) -> None:
            work = [(v, iter(sorted(graph[v])))]
            index[v] = low[v] = len(index)
            stack.append(v)
            on.add(v)
            while work:
                x, it = work[-1]
                w = next(it, None)
                if w is None:
                    work.pop()
                    if work:
                        low[work[-1][0]] = min(low[work[-1][0]], low[x])
                    if low[x] == index[x]:
                        comp = []
                        while True:
                            y = stack.pop()
                            on.discard(y)
                            comp.append(y)
                            if y == x:
                                break
                        comps.append(comp)
                elif w not in index:
                    index[w] = low[w] = len(index)
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(sorted(graph[w]))))
                elif w in on:
                    low[x] = min(low[x], index[w])
        for v in nodes:
            if v not in index:
                visit(v)
        for comp in comps:
            if len(comp) == 1 and comp[0] not in graph[comp[0]]:
                continue
            key = frozenset(comp)
            if key in seen:
                continue
            seen.add(key)
            start = min(comp, key=lambda n: line.get(n, 0))
            # the shortest way round from the first-declared relation
            prev: dict[str, str] = {}
            frontier, ring = [start], []
            while frontier and not ring:
                nxt = []
                for x in frontier:
                    for w in sorted(graph[x] & key):
                        if w == start:
                            ring = [x]
                            break
                        if w not in prev:
                            prev[w] = x
                            nxt.append(w)
                    if ring:
                        break
                frontier = nxt
            while ring[-1] != start:
                ring.append(prev[ring[-1]])
            ring.reverse()
            rest = sorted(key - set(ring), key=lambda n: line.get(n, 0))
            where = f" on alt path {'/'.join(path)}" if path else ""
            lt.err(line.get(start, 0), "cycle",
                   f"{' -> '.join(ring + [start])}{where}"
                   + (f", with {' '.join(rest)} on another cycle through them" if rest else "")
                   + ": a program is a DAG of relations")


def fix_labels(text: str) -> str:
    """The text with each later branch's remaking of an exported label made
    a naming, and each branch-local label that reuses another variable's
    name renamed with a digit."""
    for _ in range(8):
        lt = Linter(Path("-"), text)
        lt.run()
        if not lt.fixes:
            break
        for pos in sorted(lt.fixes, reverse=True):
            n, new = lt.fixes[pos]
            text = text[:pos] + new + text[pos + n:]
    return text


PLAUSIBILITY = {"ordinary", "variant", "borderline", "foreign"}
TYPES = {"Color", "number", "Dir", "Axis", "Position", "DiagDir", "Ident", "Sense", "D4", "C4", "Sym", "Offset",
         "DiagAxis", "Box", "Dir8", "Axis4", "Example"}
DERIVATIONS = set(libmap.DERIVATIONS.values())
TOP_RANK = {"representative": 0, "param": 1, "exclude": 2, "approximated": 3, "alts": 3}
WITNESS_PARTS = {"relaxed", "separates", "assign", "input", "output"}


def arcdata_errs(path: Path, imp: Linter | None = None) -> list[tuple[int, str, str]]:
    """The faults of an arcdata file: its forms, their order and heads, the
    names it takes from its arclog file, its params and its witnesses."""
    errs: list[tuple[int, str, str]] = []
    text = read_file(path)
    try:
        forms = read(text)
    except SyntaxError as e:
        return [(0, "syntax", str(e))]
    if imp is None and path.with_suffix(".arclog").exists():
        imp = Linter(path.with_suffix(".arclog"))
        imp.run()
    err = lambda line, code, msg: errs.append((line, code, msg))   # noqa: E731

    # the names the arclog file declares
    alt_names: set[str] = set()
    alts_of: dict[str, set[str]] = {}
    input_slugs: set[str] = set()
    approx_slugs: set[str] = set()
    claim_forms: list[L] = []
    if imp is not None:
        iforms = read(imp.text)
        for k, v in alts_map(iforms).items():
            alts_of[k] = set(v)
            alt_names |= v
        for a in (x for f in iforms for x in walk(f)):
            if isinstance(a, L) and a.head == "ALTS" and len(a.items) > 3 and isinstance(a.items[1], Sym) \
                    and isinstance(a.items[3], Sym):
                alts_of.setdefault(a.items[1].text, set()).add(a.items[3].text)   # the concept's name
                alt_names.add(a.items[3].text)
        for f in iforms:
            for a in walk(f):
                if isinstance(a, L) and a.head in ("DET_OR_RULE", "RULE_OR_DET") and len(a.items) > 1 \
                        and isinstance(a.items[1], Sym):
                    r = a.items[1].text
                    props = [x.text for x in a.items[2:] if isinstance(x, Sym) and x.text[:1].isupper()]
                    body = any(isinstance(x, L) and x.head not in ("ONE", "SET") for x in a.items[2:])
                    # `$Stored` selects each stored reading of a line with a stored reading per proposer
                    sides = {f"{r}=$Stored", f"{r}=$Derived"} | {f"{r}={p}" for p in props}
                    if len(props) > 1 and not body:
                        sides |= {f"{r}=$Stored.{p}" for p in props}
                    alts_of[r] = sides
                    alt_names |= sides
        claim_forms = claims_of(iforms)
        input_slugs = {f.items[1].text for f in claim_forms if f.head == "INPUT" and len(f.items) > 1}
        approx_slugs = {f.items[1].text for f in claim_forms if f.head == "OUTPUT" and len(f.items) > 1
                        and any(isinstance(x, L) and x.head == "APPROXIMATED" for x in f.items[2:])}

    # the top level
    rank = -1
    rep = None
    for f in forms:
        if not isinstance(f, L):
            continue
        if f.head not in TOP_RANK:
            err(f.line, "arcdata-head", f"({f.head} ...) is no top-level form of an arcdata file")
            continue
        if TOP_RANK[f.head] < rank:
            err(f.line, "arcdata-order", f"({f.head} ...) stands after a later kind of form: representative, "
                "param, exclude, then approximated and alts")
        rank = max(rank, TOP_RANK[f.head])
        if f.head == "representative":
            rep = f
            it = f.items
            if not (2 <= len(it) <= 3 and isinstance(it[1], Sym) and re.fullmatch(r"[0-9a-f]{8}", it[1].text)
                    and all(isinstance(x, Sym) for x in it[2:])):
                err(f.line, "representative", "(representative <task_id> [<name>])")
            elif len(it) == 3 and it[2].text not in alt_names:
                err(f.line, "arcdata-name", f"{it[2].text}: the arclog file has no alt of this name")
    for f in forms:
        for a in walk(f):
            if isinstance(a, L) and a.head == "param" and a is not f:
                err(a.line, "param", "every param form stands at the top level")
    if imp is not None:
        for c in claim_forms:
            has = len(c.items) > 2 and isinstance(c.items[2], Str)
            if rep is not None and has:
                err(c.line, "claim-text", f"{imp.path.name}:{c.line}: {c.items[1].text}: a representative's "
                    "sibling's blocks carry the slug with no text")
            elif rep is None and not has:
                err(c.line, "claim-text", f"{imp.path.name}:{c.line}: {flat(c.items[1])}: a claim block has a text")

    # params
    def check_rows(f: L, name: str, types: list[str], rows: list) -> None:
        for r in rows:
            if isinstance(r, L) and r.head in DERIVATIONS:
                continue
            if isinstance(r, L) and r.head == "grid":
                vals = []
            elif isinstance(r, L) and not r.head or (isinstance(r, L) and r.items and not isinstance(r.items[0], L)
                                                     and r.head not in ("grid",)):
                vals = r.items
            else:
                vals = r.items if isinstance(r, L) else None
            if vals is None:
                err(getattr(r, "line", f.line), "param", f"{name}: a row is a list of values")
                continue
            grid = [i for i, v in enumerate(vals) if isinstance(v, L) and v.head == "grid"]
            pos = [i for i, t in enumerate(types) if t in ("Position", "Offset")]
            if isinstance(r, L) and r.head == "grid":
                if not pos or pos[0] != 0:
                    err(r.line, "param", f"{name}: a grid gives the Position column, and values before it fill the "
                        "columns before the position")
                continue
            if pos and not grid and "Position" in types:
                err(r.line, "param-grid", f"{name}: a relation with a Position column is given as a grid")
                continue
            if grid:
                if not pos or grid[0] != pos[0] or len(vals) != pos[0] + 1:
                    err(r.line, "param", f"{name}: the values before the grid fill the columns before the position")
                continue
            if len(vals) != len(types):
                err(r.line, "param", f"{name}: a row of {len(vals)} values, and the form gives {len(types)} column types")

    for f in forms:
        if not (isinstance(f, L) and f.head == "param"):
            continue
        it = f.items
        if len(it) < 3 or not isinstance(it[1], Sym):
            err(f.line, "param", "(param <name> <type or (types)> <rows>)")
            continue
        name = it[1].text
        if imp is not None and name.partition(".")[0] not in imp.declared:
            err(f.line, "arcdata-name", f"{name}: the arclog file declares no relation of this name")
        t = it[2]
        if isinstance(t, Sym) and t.text in TYPES:
            types, rows = [t.text], it[3:]
        elif isinstance(t, L) and t.items and all(isinstance(x, Sym) and x.text in TYPES for x in t.items):
            types, rows = [x.text for x in t.items], it[3:]
        else:
            err(f.line, "param-types", f"{name}: the column types follow the name, one type or a list")
            continue
        if not rows:
            err(f.line, "param", f"{name}: no rows")
        if imp is not None and name in imp.set_marked and len(rows) < 2:
            err(f.line, "set", f"{name}: the clause at line {imp.set_marked[name]} ends in (SET), and a param of "
                f"{len(rows)} row gives it one value already")
        check_rows(f, name, types, rows)

    # exclude
    for f in forms:
        if isinstance(f, L) and f.head == "exclude":
            it = f.items
            if not (len(it) == 3 and isinstance(it[1], L) and isinstance(it[2], Str)):
                err(f.line, "exclude", "(exclude (<alt> ...) \"<reason>\")")
            elif alt_names:
                for x in it[1].items:
                    if not (isinstance(x, Sym) and x.text in alt_names):
                        err(f.line, "arcdata-name", f"exclude {flat(x)}: the arclog file has no alt of this name")

    # alts, approximated and witnesses
    full: dict[str, tuple[str, str]] = {}

    def witness(w: L, ctx: str) -> None:
        it = w.items
        if len(it) < 4 or not all(isinstance(x, Sym) for x in it[1:4]):
            err(w.line, "witness", "(witness <id> <plausibility> <verdict> ...)")
            return
        wid, pl, vd = it[1].text, it[2].text, it[3].text
        if pl not in PLAUSIBILITY:
            err(w.line, "witness", f"witness {wid}: {pl} is no plausibility")
        if vd not in {"concept", "any", "other"} and alt_names and vd not in alt_names:
            err(w.line, "witness", f"witness {wid}: verdict {vd} is concept, an alt's name, any or other")
        body = [x for x in it[4:] if isinstance(x, L)]
        if not body:
            if wid in full and full[wid] != (pl, vd):
                err(w.line, "witness-ref", f"witness {wid}: the full form gives {' '.join(full[wid])}")
            return
        if wid in full:
            err(w.line, "witness-id", f"witness {wid}: a second witness given in full under this id")
        full[wid] = (pl, vd)
        nameless = 0
        for x in body:
            if x.head not in WITNESS_PARTS:
                err(x.line, "arcdata-head", f"({x.head} ...) is no part of a witness")
            elif x.head == "relaxed":
                if not (len(x.items) == 2 and isinstance(x.items[1], Sym)):
                    err(x.line, "witness", "(relaxed <slug>)")
                elif input_slugs and x.items[1].text not in input_slugs:
                    err(x.line, "arcdata-name", f"relaxed {x.items[1].text}: the arclog file has no INPUT claim "
                        "of this slug")
            elif x.head == "separates" and not (len(x.items) == 2 and isinstance(x.items[1], Str)):
                err(x.line, "witness", "(separates \"<prose>\")")
            elif x.head == "assign":
                if not all(isinstance(r, L) for r in x.items[2:]):
                    err(x.line, "assign", "assign gives rows in the form a param form takes")
                if len(x.items) > 1 and isinstance(x.items[1], Sym) and imp is not None \
                        and x.items[1].text.partition(".")[0] not in imp.declared:
                    err(x.line, "arcdata-name", f"assign {x.items[1].text}: the arclog file declares no relation "
                        "of this name")
            elif x.head == "output":
                names = [y for y in x.items[1:] if not (isinstance(y, L) and y.head == "grid")
                         and not (isinstance(y, Sym) and y.text == "undefined")]
                if not names:
                    nameless += 1
                for y in names:
                    for n in ([y] if isinstance(y, Sym) else y.items):
                        if isinstance(n, Sym) and n.text != "concept" and alt_names and n.text not in alt_names:
                            err(x.line, "arcdata-name", f"output {n.text}: the arclog file has no alt of this name")
        if vd == "other" and nameless != 1:
            err(w.line, "witness-other", f"witness {wid}: with the verdict other, one output form with no name holds "
                "the judged grid")
        if vd != "other" and nameless:
            err(w.line, "witness-other", f"witness {wid}: an output form with no name stands only under the verdict other")
        for part in ("separates", "input"):
            if part not in {x.head for x in body}:
                err(w.line, f"witness-no-{part}", f"witness {wid} has no {part}")

    def alt_form(a: L, owner: str | None, outer: set[str]) -> int:
        n = 0
        it = a.items
        if len(it) < 2 or not isinstance(it[1], Sym):
            err(a.line, "alts", "(alt <name> ...)")
            return 0
        nm = it[1].text
        if alts_of and owner is not None and nm not in alts_of.get(owner, set()) and not outer:
            err(a.line, "arcdata-name", f"alt {nm}: no alt of {owner} has this name")
        if outer and alts_of and any(nm in alts_of.get(o, set()) for o in outer):
            err(a.line, "alts", f"alt {nm}: a nested alt form is a combination with an alt of another ALTS form")
        mine = {k for k, v in alts_of.items() if nm in v}
        for x in it[2:]:
            if isinstance(x, L) and x.head == "witness":
                witness(x, nm)
                n += 1
            elif isinstance(x, L) and x.head == "alt":
                n += alt_form(x, None, outer | mine)
            else:
                err(getattr(x, "line", a.line), "arcdata-head", "an alt form holds witness and alt forms")
        if not n:
            err(a.line, "alts-empty", f"alt {nm} holds no witness: an alts form holds an alt form per alt that has one")
        return n

    for f in forms:
        if not isinstance(f, L):
            continue
        if f.head == "alts":
            it = f.items
            if len(it) < 2 or not isinstance(it[1], Sym):
                err(f.line, "alts", "(alts <name> (alt ...) ...)")
                continue
            if alts_of and it[1].text not in alts_of:
                err(f.line, "arcdata-name", f"alts {it[1].text}: the arclog file has no ALTS form or _OR_ line "
                    "of this name")
            n = 0
            for a in it[2:]:
                if isinstance(a, L) and a.head == "alt":
                    n += alt_form(a, it[1].text, set())
                else:
                    err(getattr(a, "line", f.line), "arcdata-head", "an alts form holds alt forms")
            if not n:
                err(f.line, "alts-empty", f"alts {it[1].text} holds no witness, and an ALTS form with no witness "
                    "has no alts form")
        elif f.head == "approximated":
            it = f.items
            if len(it) < 2 or not isinstance(it[1], Sym):
                err(f.line, "approximated", "(approximated <slug> (witness ...) ...)")
                continue
            if imp is not None and it[1].text not in approx_slugs:
                err(f.line, "arcdata-name", f"approximated {it[1].text}: no OUTPUT claim of this slug carries an "
                    "APPROXIMATED form")
            for w in it[2:]:
                if isinstance(w, L) and w.head == "witness":
                    witness(w, it[1].text)
                else:
                    err(getattr(w, "line", f.line), "arcdata-head", "an approximated form holds witness forms")
    # a witness with no body is one an earlier form gives in full: in file order
    seen: set[str] = set()
    for f in forms:
        for w in walk(f):
            if isinstance(w, L) and w.head == "witness" and len(w.items) > 1 and isinstance(w.items[1], Sym):
                if any(isinstance(x, L) for x in w.items[4:]):
                    seen.add(w.items[1].text)
                elif w.items[1].text not in seen:
                    err(w.line, "witness-ref", f"witness {w.items[1].text} has no body, and no earlier form gives "
                        "it in full")

    # grid rows: one per line, two spaces in from the form that holds the grid
    starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def indent(pos: int) -> tuple[int, int]:
        import bisect
        k = bisect.bisect_right(starts, pos) - 1
        line = text[starts[k]:text.find("\n", starts[k]) if "\n" in text[starts[k]:] else len(text)]
        return k, len(line) - len(line.lstrip(" "))

    for f in forms:
        for holder in walk(f):
            if not isinstance(holder, L):
                continue
            for g in holder.items:
                if not (isinstance(g, L) and g.head == "grid"):
                    continue
                hl, hi = indent(g.start)
                rows = [r for r in g.items[1:] if isinstance(r, L)]
                lines = [indent(r.start)[0] for r in rows]
                for r, ln in zip(rows, lines):
                    k, ind = indent(r.start)
                    col = r.start - starts[k]
                    if lines.count(ln) > 1 or ln == hl or col != hi + 2 or ind != hi + 2:
                        err(r.line, "grid-layout", "a grid's rows stand one per line, two spaces in from the form "
                            "that holds the grid")
                        break
    return errs


def lint_group(paths: list[Path]) -> list[tuple[Path, list]]:
    """Each path's violations, an arcdata file's read with the Linter of
    the group's arclog file."""
    linted: dict[Path, Linter] = {}
    out = []
    for p in sorted(paths, key=lambda x: x.suffix == ".arcdata"):
        try:
            if p.suffix == ".arcdata":
                errs = arcdata_errs(p, linted.get(p.with_suffix(".arclog")))
            else:
                lt = Linter(p)
                lt.run()
                errs = lt.errs
                linted[p] = lt
        except Stale as e:
            errs = [(0, "stale", str(e))]
        out.append((p, errs))
    return out


# ---------------------------------------------------------------- safety

BODY_FORMS = {"RULE", "DET", "DET_OR_RULE", "RULE_OR_DET", "RIGID_DET"}


def bare_label(t: str) -> str:
    return t.lstrip("*^")


def is_const(t: str) -> bool:
    b = bare_label(t)
    return b.lstrip("-").isdigit() or b[:1] in ("$", "{") or b == "_"


def site_pairs(x) -> list[tuple[str, str]]:
    """The (column path, label) pairs of one site of an atom."""
    if isinstance(x, Sym):
        return [(bare_label(x.text), x.text)]
    if not isinstance(x, L) or not x.head:
        return []
    col, args = x.head[1:], x.items[1:]
    if len(args) == 1 and isinstance(args[0], Sym):
        return [(col, args[0].text)]
    out: list[tuple[str, str]] = []
    for a in args:
        if isinstance(a, Sym):
            out.append((col + "." + bare_label(a.text), a.text))
        else:
            out.extend((col + "." + p, t) for p, t in site_pairs(a))
    return out


def form_labels(f) -> list[str]:
    """The labels a form names at any depth, with their marks."""
    if isinstance(f, Sym):
        return [] if is_const(f.text) else [f.text]
    if not isinstance(f, L):
        return []
    out: list[str] = []
    for i, x in enumerate(f.items):
        if i == 0 and isinstance(x, Sym):
            continue
        out.extend(form_labels(x))
    return out


def outer_labels(forms) -> set[str]:
    """The labels of forms that no `*` made inside them marks: they join from outside."""
    toks = [t for f in forms for t in form_labels(f)]
    made = {bare_label(t) for t in toks if t.startswith("*")}
    return {bare_label(t) for t in toks} - made


class BoundLabels:
    """The labels bound so far, closed under the `=` pairs seen."""

    def __init__(self, names=(), eqs=()):
        self.names = set(names)
        self.eqs = list(eqs)

    def copy(self) -> "BoundLabels":
        return BoundLabels(self.names, self.eqs)

    def add(self, labels) -> None:
        self.names |= {bare_label(t) for t in labels if not is_const(t)}
        self.close()

    def has(self, t: str) -> bool:
        return is_const(t) or bare_label(t) in self.names

    def close(self) -> None:
        moved = True
        while moved:
            moved = False
            for a, b in self.eqs:
                for x, y in ((a, b), (b, a)):
                    if all(self.has(t) for t in x) and not all(self.has(t) for t in y):
                        self.names |= {bare_label(t) for t in y if not is_const(t)}
                        moved = True

    def equate(self, a: list[str], b: list[str]) -> None:
        self.eqs.append((a, b))
        self.close()


def mode_gap(a: L, g: BoundLabels) -> str | None:
    """None where one mode of an algebra atom has its columns given and bound, else why not."""
    cols: dict[str, list[str]] = {}
    for s in a.items[1:]:
        for path, tok in site_pairs(s):
            cols.setdefault(path.split(".")[0].lower(), []).append(tok)
    best = None
    for m in ALGEBRA_MODES[a.head]:
        miss = sorted(c for c in m if c not in cols)
        loose = sorted(c for c in m if c in cols and not all(g.has(t) for t in cols[c]))
        if not miss and not loose:
            return None
        if best is None:
            best = ", ".join(f"{c} is left out" for c in miss) + (", " if miss and loose else "") \
                + ", ".join(f"{c} is not bound" for c in loose)
    return best


def bind_items(items, g: BoundLabels, found: list[tuple[int, str]]) -> None:
    """The items of one list in written order; `found` takes each break of the rule."""
    for it in items:
        if not isinstance(it, L):
            continue
        h = it.head
        if h is None:
            bind_items(it.items, g, found)
        elif h in OPS:
            sides = [form_labels(x) if isinstance(x, L) else ([] if is_const(x.text) else [x.text])
                     for x in it.items[1:] if isinstance(x, (Sym, L))]
            if h == "=" and len(sides) == 2:
                g.equate(sides[0], sides[1])
        elif h == "ONE":
            pass
        elif h == "NOT":
            inner = [x for x in it.items[1:] if isinstance(x, L)]
            late = sorted(outer_labels(inner) - g.names - {t for t in outer_labels(inner) if is_const(t)})
            if late:
                found.append((it.line, f"NOT stands before the atoms that bind {', '.join(late)}"))
            bind_items(inner, g.copy(), found)
        elif h == "ALL":
            parts = [x for x in it.items[1:] if isinstance(x, L)]
            late = sorted(t for t in outer_labels(parts) if not g.has(t))
            if late:
                found.append((it.line, f"ALL stands before the atoms that bind {', '.join(late)}"))
            inner = g.copy()
            for p in parts:
                bind_items(p.items, inner, found)
        elif h == "OR":
            outs = []
            for b in it.items[1:]:
                if isinstance(b, L):
                    gb = g.copy()
                    bind_items(b.items, gb, found)
                    outs.append(gb.names)
            if outs:
                g.names |= set.intersection(*outs)
                g.close()
        elif h == "IF":
            parts = [x for x in it.items[1:] if isinstance(x, L)]
            if len(parts) == 3:
                gt = g.copy()
                bind_items(parts[0].items, gt, found)
                gth = gt.copy()
                bind_items(parts[1].items, gth, found)
                ge = g.copy()
                bind_items(parts[2].items, ge, found)
                g.names |= gth.names & ge.names
                g.close()
        else:
            if h in ALGEBRA_MODES and h in LIB.top:
                why = mode_gap(it, g)
                if why:
                    found.append((it.line, f"{flat(it)}: no mode of {h} is given and bound by the atoms "
                                  f"before it ({why})"))
            g.add(t for s in it.items[1:] for _, t in site_pairs(s))


def bodies_of(forms, keys=()):
    """(line, name, items, bound labels) of each body in the forms."""
    out: list[tuple[int, str, list, set[str]]] = []

    def inputs(f: L, xs, key_labels) -> None:
        for x in xs:
            if isinstance(x, L) and x.head and len(x.items) > 1:
                out.append((x.line, f"{f.items[1].text}.{x.head}", x.items[2:], set(key_labels)))

    def key_body(f: L, kb: L) -> list[str]:
        out.append((kb.line, f"{f.items[1].text} key", kb.items, set()))
        return sorted({bare_label(t) for t in form_labels(kb) if t.startswith("^")})

    def walk(fs) -> None:
        for f in fs:
            if not isinstance(f, L) or not f.head:
                continue
            h = f.head
            if h in ("INPUT", "OUTPUT", "ALTS", "ALT", "DEMO_RULE"):
                walk(f.items[1:])
            elif h in BODY_FORMS and len(f.items) > 1 and isinstance(f.items[1], Sym):
                out.append((f.line, f.items[1].text, f.items[2:], set()))
            elif h in ("INIT", "DEMONSTRATED") and len(f.items) > 1 and isinstance(f.items[1], Sym):
                for x in f.items[3:] if h == "INIT" else f.items[2:]:
                    if not isinstance(x, L) or not x.head:
                        continue
                    if x.head == "key" and len(x.items) > 1 and isinstance(x.items[1], L):
                        inputs(f, x.items[2:], key_body(f, x.items[1]))
                    elif x.head == "DEMO_RULE":
                        walk([x])
                    else:
                        inputs(f, [x], ())
            elif h == "CHOOSE" and len(f.items) > 1 and isinstance(f.items[1], Sym):
                for x in f.items[2:]:
                    if not isinstance(x, L) or not x.head:
                        continue
                    if x.head == "for" and len(x.items) > 1 and isinstance(x.items[1], L):
                        ks = key_body(f, x.items[1])
                        for inp in x.items[2:]:
                            if isinstance(inp, L) and inp.head:
                                out.append((inp.line, f"{f.items[1].text}.{inp.head}", inp.items[1:], set(ks)))
                    else:
                        out.append((x.line, f"{f.items[1].text}.{x.head}", x.items[1:], set()))

    walk(forms)
    return out


def safety(lt: Linter, forms) -> None:
    """In each body, in written order, an algebra relation atom has a mode
    whose columns the atoms before it bind, over the `=` classes, with 0
    bound; a NOT and an ALL stand after the atoms that bind their
    outer labels."""
    for line, name, items, labels in bodies_of(forms):
        found: list[tuple[int, str]] = []
        bind_items(items, BoundLabels(labels), found)
        if found:
            more = f" (and {len(found) - 1} more)" if len(found) > 1 else ""
            lt.err(found[0][0], "safety", f"{name}: {found[0][1]}{more}")


def main(argv: list[str]) -> None:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return
    show_all = "--all" in argv
    argv = [a for a in argv if a != "--all"]
    paths = [Path(a) for a in argv] or (sorted(GEN.glob("*.arclog")) + sorted(GEN.parent.glob("*.arcscene"))
                                        + sorted(GEN.glob("*.arcdata")))
    counts: Counter = Counter()
    files: dict[str, set] = defaultdict(set)
    quiet = len(paths) > 20 and not show_all
    shown: Counter = Counter()
    # an arcdata file is linted with its arclog file's Linter, so the two go to one worker
    groups: dict[Path, list[Path]] = defaultdict(list)
    for p in paths:
        groups[p.with_suffix(".arclog") if p.suffix == ".arcdata" else p].append(p)
    order = sorted(groups.values(), key=lambda g: -sum(x.stat().st_size for x in g if x.exists()))
    if len(order) > 20:
        from concurrent.futures import ProcessPoolExecutor

        from engine.pool import pool_size
        with ProcessPoolExecutor(min(len(order), pool_size())) as pool:
            found = dict(x for got in pool.map(lint_group, order) for x in got)
    else:
        found = dict(x for g in order for x in lint_group(g))
    for p in paths:
        for line, code, msg in found[p]:
            counts[code] += 1
            files[code].add(p.name)
            if not quiet or shown[code] < 4:
                shown[code] += 1
                print(f"{p}:{line}: {code}: {msg}")
    print()
    for code, n in counts.most_common():
        print(f"  {code:18} {n:6} in {len(files[code])} files")
    for suffix in sorted({p.suffix for p in paths}):
        some = [p for p in paths if p.suffix == suffix]
        clean = sum(1 for p in some if not any(p.name in f for f in files.values()))
        print(f"{clean} of {len(some)} {suffix} files clean")


if __name__ == "__main__":
    main(sys.argv[1:])
