//! The canonical form of a node and its hash.
//!
//! A body's canonical form is the same under a reorder of its atoms, a
//! reorder of the branches of an `OR`, and a renaming of its labels. The
//! labeling comes from individualization–refinement: color refinement with
//! the column paths as edge labels, then the first largest cell that is not
//! a singleton, with a cap of [`SEARCH_NODE_CAP`] search nodes on the search
//! of each label scope. A body that reaches the cap takes the least labeling
//! the search has found.
//!
//! A node's canonical hash names each relation it reads as the file writes
//! it, [`AsWritten`]. The resolved content of a node in one case program, in
//! which each derived relation stands for its own content, is
//! [`crate::resolver::ResolvedProgram::content`], which writes the same
//! canonical form through a [`NameWriter`] of the resolver.

use std::hash::Hasher;

use super::path::{NodePath, PathStep};
use super::*;
use crate::hash::{StableHash, StableHashMap, StableHasher};

/// The provisional cap on the search nodes of individualization–refinement,
/// for the search of each label scope.
///
/// The cap guards synthesized bodies, whose symmetry the corpus does not
/// show. The corpus's search reaches at most 13 nodes.
pub const SEARCH_NODE_CAP: u32 = 1000;

/// A node kind that has a canonical form.
pub trait Canonical {
    /// Writes the value's canonical form into `out`, with each name the
    /// value reads written by `names`.
    ///
    /// The bytes written are equal for two values exactly where their
    /// canonical forms are equal.
    fn write_canonical(&self, out: &mut CanonicalWriter, search: &mut SearchBudget, names: &dyn NameWriter);

    /// Whether two values have equal canonical forms.
    fn canonical_eq(&self, other: &Self) -> bool;
}

/// How a canonical form writes each relation a node reads: as the file
/// writes it, [`AsWritten`], for a node's canonical hash, or, in the
/// resolver, as the resolved content the name stands for, for
/// [`crate::resolver::ResolvedContent`], in which a derived relation's
/// content is its clause.
pub trait NameWriter {
    /// Writes `relation` into `out`.
    fn write_name(&self, relation: &super::RelationRef, out: &mut CanonicalWriter);

    /// Writes a column of `relation` into `out`: a column that a site names,
    /// or that a clause gives the relation it derives. `column` is the
    /// column's path: its name, or, for a site on a field of a record, the
    /// record's column and then the field, as `[key, P]` for `(:P P2)` in
    /// `(:key (:P P2))`. The resolver writes its canonical position, as
    /// [`crate::resolver::ColumnPosition`] gives, so that names do not enter
    /// the resolved content. An instance input's head sites name columns of
    /// a lib port, which no [`super::RelationRef`] names, so they are written
    /// as the file writes them and never pass through this method.
    fn write_column(&self, relation: &super::RelationRef, column: &[super::ColumnName], out: &mut CanonicalWriter);
}

/// The relation whose columns a `DEMO_RULE` form's fields are: its
/// `&prediction` (`docs/arclog/arclog.md#demonstrated`).
fn prediction() -> RelationRef {
    RelationRef::Declared(RelationName(DeclaredName::Written(format!("{}prediction", crate::read::spelling::DECLARED_MARK).into())))
}


/// The writer of a canonical form: it keeps the bytes written, so that two
/// forms whose hashes match are compared by their bytes.
///
/// The encoding is self-delimiting: each value opens with a tag of its kind,
/// and each list and each string with its length, so two different values
/// never write the same bytes.
#[derive(Clone, Debug, Default)]
pub struct CanonicalWriter {
    bytes: Vec<u8>,
}

impl CanonicalWriter {
    /// Writes `bytes` to the form.
    pub fn write(&mut self, bytes: &[u8]) {
        self.bytes.extend_from_slice(bytes);
    }

    /// The form written, with its hash under [`crate::hash::StableHasher`].
    pub fn finish(self) -> CanonicalForm {
        let mut hasher = StableHasher::new();
        hasher.write(&self.bytes);
        CanonicalForm { hash: hasher.finish128(), bytes: self.bytes.into() }
    }

    fn tag(&mut self, tag: Tag) {
        self.bytes.push(tag as u8);
    }

    fn byte(&mut self, byte: u8) {
        self.bytes.push(byte);
    }

    fn int(&mut self, n: u32) {
        self.write(&n.to_le_bytes());
    }

    fn len(&mut self, n: usize) {
        self.int(u32::try_from(n).expect("a list of a node has fewer than 2^32 members"));
    }

    fn flag(&mut self, flag: bool) {
        self.bytes.push(u8::from(flag));
    }

    fn text(&mut self, text: &str) {
        self.len(text.len());
        self.write(text.as_bytes());
    }

    /// Writes the bytes of a form written apart, with their length.
    fn nested(&mut self, bytes: &[u8]) {
        self.len(bytes.len());
        self.write(bytes);
    }

    fn option<T>(&mut self, value: Option<T>, write: impl FnOnce(&mut Self, T)) {
        match value {
            None => self.tag(Tag::None),
            Some(value) => {
                self.tag(Tag::Some);
                write(self, value);
            }
        }
    }

    fn declared(&mut self, name: &DeclaredName) {
        match name {
            DeclaredName::Written(text) => {
                self.tag(Tag::Written);
                self.text(text);
            }
            DeclaredName::Slot(slot) => {
                self.tag(Tag::Slot);
                self.int(*slot);
            }
        }
    }

    fn column(&mut self, name: &ColumnName) {
        match name {
            ColumnName::Written(text) => {
                self.tag(Tag::Written);
                self.text(text);
            }
            ColumnName::Slot(slot) => {
                self.tag(Tag::Slot);
                self.int(*slot);
            }
        }
    }

    fn column_path(&mut self, path: &[ColumnName]) {
        self.len(path.len());
        for name in path {
            self.column(name);
        }
    }
}

/// The tag of each kind of value a canonical form writes.
#[derive(Clone, Copy)]
#[repr(u8)]
enum Tag {
    None,
    Some,
    Written,
    Slot,
    Fact,
    Lib,
    Declared,
    Output,
    DefinedPort,
    InstanceOwner,
    RigidDetOwner,
    PortStep,
    PartStep,
    PoseStep,
    Program,
    Claim,
    Clause,
    Instance,
    Choose,
    RigidDet,
    Demonstrated,
    Alts,
    Alt,
    AltForm,
    AltNested,
    Body,
    Atom,
    NotAtom,
    NotForm,
    Constraint,
    Or,
    If,
    All,
    Site,
    ArgLabel,
    ArgField,
    Fresh,
    Join,
    Key,
    Zero,
    KeyClause,
    KeyBody,
    Input,
    DemoRule,
    Param,
    Rows,
    Grids,
    Derivation,
    Integer,
    Orientation,
    List,
    Arcdata,
    AltsRecord,
    ApproximatedRecord,
    Concept,
    AltVerdict,
    Any,
    Other,
    Undefined,
    // The vertex colors and edge labels of a scope's graph.
    Root,
    Label,
    Member,
    Branch,
    Part,
    Head,
    One,
    Column,
    Form,
}

/// A canonical form, as its bytes and their hash.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CanonicalForm {
    pub hash: StableHash,
    pub bytes: std::sync::Arc<[u8]>,
}

impl std::hash::Hash for CanonicalForm {
    /// Hashes `hash` alone, so a lookup hashes no bytes.
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.hash.hash(state);
    }
}

/// Each name as the file writes it.
#[derive(Clone, Copy, Debug, Default)]
pub struct AsWritten;

impl NameWriter for AsWritten {
    fn write_name(&self, relation: &super::RelationRef, out: &mut CanonicalWriter) {
        match relation {
            RelationRef::Fact(fact) => {
                out.tag(Tag::Fact);
                out.byte(*fact as u8);
            }
            RelationRef::Lib(crate::registry::LibName(name)) => {
                out.tag(Tag::Lib);
                out.text(name);
            }
            RelationRef::Declared(RelationName(name)) => {
                out.tag(Tag::Declared);
                out.declared(name);
            }
            RelationRef::Output(name) => {
                out.tag(Tag::Output);
                match &name.of {
                    OutputOwner::Instance(InstanceName(owner)) => {
                        out.tag(Tag::InstanceOwner);
                        out.declared(owner);
                    }
                    OutputOwner::RigidDet(RigidDetName(owner)) => {
                        out.tag(Tag::RigidDetOwner);
                        out.declared(owner);
                    }
                }
                out.len(name.path.len());
                for step in name.path.iter() {
                    match step {
                        OutputStep::Port(PortName(port)) => {
                            out.tag(Tag::PortStep);
                            out.text(port);
                        }
                        OutputStep::Part(part) => {
                            out.tag(Tag::PartStep);
                            out.declared(part);
                        }
                        OutputStep::Pose => out.tag(Tag::PoseStep),
                    }
                }
            }
            RelationRef::DefinedPort(PortName(port)) => {
                out.tag(Tag::DefinedPort);
                out.text(port);
            }
        }
    }

    fn write_column(&self, _relation: &super::RelationRef, column: &[super::ColumnName], out: &mut CanonicalWriter) {
        out.column_path(column);
    }
}

/// The search nodes that the search of the label scope in progress has
/// left, and whether the search of any scope of the value reached the cap.
/// Each scope's search starts with [`SEARCH_NODE_CAP`] nodes, and a search
/// that runs inside a leaf of another spends none of that other's nodes.
#[derive(Clone, Debug)]
pub struct SearchBudget {
    pub remaining: u32,
    /// Set when the search of a scope reached the cap, which is an alert.
    pub reached: bool,
}

impl SearchBudget {
    /// A budget of [`SEARCH_NODE_CAP`] nodes, with no scope at the cap.
    pub fn new() -> Self {
        SearchBudget { remaining: SEARCH_NODE_CAP, reached: false }
    }
}

impl Default for SearchBudget {
    fn default() -> Self {
        SearchBudget::new()
    }
}

/// The canonical labeling of one scope: for each label of the scope, its
/// position in the canonical form.
#[derive(Clone, Debug)]
pub struct CanonicalLabeling {
    pub positions: Box<[(super::LabelId, u32)]>,
    /// Whether the search reached [`SEARCH_NODE_CAP`], so that the labeling
    /// is the least one the search found.
    pub reached_cap: bool,
}

/// The labels that one canonical labeling numbers: those of a label scope,
/// as [`LabelId`] gives a scope, or those of a node whose own hash is taken
/// apart from its scope.
#[derive(Clone, Copy, Debug)]
pub enum LabelScope<'a> {
    Clause(&'a Clause),
    Instance(&'a Instance),
    Choose(&'a Choose),
    RigidDet(&'a RigidDet),
    /// A `DEMONSTRATED` form's key clause and inputs, apart from its
    /// `DEMO_RULE` forms.
    DemonstratedKey(&'a Demonstrated),
    DemoRule(&'a DemoRule),
    Body(&'a Body),
    Atom(&'a Atom),
    KeyClause(&'a KeyClause),
    InstanceInput(&'a InstanceInput),
}

/// The canonical labeling of `scope`, by individualization–refinement, with
/// the column paths as edge labels as `names` writes them: as written for a
/// node's hash, [`AsWritten`], or as the resolved positions for the
/// resolved content. It takes a scope in place of one body, since a body
/// alone does not give the labels of the scope's head sites.
pub fn canonical_labeling(scope: LabelScope, names: &dyn NameWriter, search: &mut SearchBudget) -> CanonicalLabeling {
    let mut cx = Context::new(search, names);
    let (labels, reached_cap) = cx.labeling(scope);
    CanonicalLabeling { positions: by_position(&labels), reached_cap }
}

/// The canonical order of one form: for each list of the form, the source
/// index at each canonical position, and for each label, its canonical
/// position. A result cached by canonical hash is held in canonical order
/// and served to each form of equal content through its own order, so the
/// cases that share a form share its check.
///
/// The labels are held for each label scope within the form, by the source
/// path of that scope's form relative to the form: the empty path for the
/// form's own scope, a `DEMONSTRATED` form's key clause and inputs among
/// them, the path of each form of a claim or an `ALT`, and the path of each
/// `DEMO_RULE` form.
#[derive(Clone, Debug)]
pub struct CanonicalOrder {
    lists: crate::hash::StableHashMap<super::path::NodePath, Box<[u32]>>,
    labels: crate::hash::StableHashMap<super::path::NodePath, Box<[(super::LabelId, u32)]>>,
}

/// The orders a write records for [`CanonicalOrder`]: each sorted list's,
/// and each scope's labels, by source path.
#[derive(Default)]
struct Recorded {
    lists: StableHashMap<NodePath, Box<[u32]>>,
    labels: StableHashMap<NodePath, Box<[(LabelId, u32)]>>,
}

impl CanonicalOrder {
    /// The canonical order of `form`.
    pub fn of(form: &super::Form, search: &mut SearchBudget) -> Self {
        let mut cx = Context::new(search, &AsWritten);
        cx.order = Some(Recorded::default());
        form_root(&mut cx, &mut CanonicalWriter::default(), form);
        let recorded = cx.order.take().expect("the order is recorded");
        CanonicalOrder { lists: recorded.lists, labels: recorded.labels }
    }

    /// The source path of the node at `canonical`, a path in canonical
    /// order, relative to the form.
    pub fn source_path(&self, canonical: &super::path::NodePath) -> super::path::NodePath {
        let mut source: Vec<PathStep> = Vec::with_capacity(canonical.0.len());
        for step in canonical.0.iter() {
            let mapped = match self.lists.get(&NodePath(source.clone().into())) {
                Some(order) => PathStep(*order.get(step.0 as usize).expect("a canonical path names a member of each list")),
                None => *step,
            };
            source.push(mapped);
        }
        NodePath(source.into())
    }

    /// The canonical path of the node at `source`, a path in source order,
    /// relative to the form.
    pub fn canonical_path(&self, source: &super::path::NodePath) -> super::path::NodePath {
        let mut canonical = Vec::with_capacity(source.0.len());
        for (depth, step) in source.0.iter().enumerate() {
            let mapped = match self.lists.get(&NodePath(source.0[..depth].into())) {
                Some(order) => {
                    let position = order.iter().position(|&index| index == step.0);
                    PathStep(position.expect("a source path names a member of each list") as u32)
                }
                None => *step,
            };
            canonical.push(mapped);
        }
        NodePath(canonical.into())
    }

    /// The label at canonical `position` of the scope whose form stands at
    /// `scope`, a source path relative to the form.
    pub fn source_label(&self, scope: &super::path::NodePath, position: u32) -> super::LabelId {
        let found = self.scope_labels(scope).iter().find(|(_, p)| *p == position);
        found.expect("a canonical position of a label of the scope").0
    }

    /// The canonical position of `label` of the scope whose form stands at
    /// `scope`, a source path relative to the form.
    pub fn canonical_label(&self, scope: &super::path::NodePath, label: super::LabelId) -> u32 {
        let found = self.scope_labels(scope).iter().find(|(l, _)| *l == label);
        found.expect("a label of the scope").1
    }

    fn scope_labels(&self, scope: &NodePath) -> &[(LabelId, u32)] {
        self.labels.get(scope).expect("the path of a label scope of the form")
    }
}

/// The hash of the canonical form of `value`.
pub fn canonical_hash<T: Canonical>(value: &T) -> StableHash {
    form_of(value).0.hash
}

/// The canonical form of `value` under [`AsWritten`] with a new
/// [`SearchBudget`], and whether its search reached the cap.
pub(super) fn form_of<T: Canonical>(value: &T) -> (CanonicalForm, bool) {
    let mut search = SearchBudget::new();
    let mut out = CanonicalWriter::default();
    value.write_canonical(&mut out, &mut search, &AsWritten);
    (out.finish(), search.reached)
}

/// Each label's canonical position.
type Labels = StableHashMap<LabelId, u32>;

fn by_position(labels: &Labels) -> Box<[(LabelId, u32)]> {
    let mut positions: Vec<(LabelId, u32)> = labels.iter().map(|(l, p)| (*l, *p)).collect();
    positions.sort_by_key(|(_, p)| *p);
    positions.into()
}

/// The state of one write: the labels of the scope being written, the
/// search budget, the name writer, the source path of the node being
/// written, relative to the form, and, for [`CanonicalOrder`], the orders
/// recorded.
struct Context<'a> {
    labels: Labels,
    search: &'a mut SearchBudget,
    names: &'a dyn NameWriter,
    path: Vec<PathStep>,
    order: Option<Recorded>,
}

impl<'a> Context<'a> {
    fn new(search: &'a mut SearchBudget, names: &'a dyn NameWriter) -> Self {
        Context { labels: Labels::default(), search, names, path: Vec::new(), order: None }
    }

    fn position(&self, label: LabelId) -> u32 {
        *self.labels.get(&label).expect("each label of a scope has a position in its labeling")
    }

    fn label(&self, out: &mut CanonicalWriter, label: LabelId) {
        out.tag(Tag::Label);
        out.int(self.position(label));
    }

    /// Runs `write` on the child at `index` of the node being written.
    fn child<R>(&mut self, index: usize, write: impl FnOnce(&mut Self) -> R) -> R {
        self.path.push(PathStep(index as u32));
        let result = write(self);
        self.path.pop();
        result
    }

    /// Writes `members`, each through `write` as the child at its index,
    /// sorted by the bytes of their forms, and records their order.
    fn sorted<T>(&mut self, out: &mut CanonicalWriter, members: &[T], write: impl Fn(&mut Self, &mut CanonicalWriter, &T)) {
        let mut forms: Vec<(Vec<u8>, u32)> = members
            .iter()
            .enumerate()
            .map(|(index, member)| {
                let mut own = CanonicalWriter::default();
                self.child(index, |cx| write(cx, &mut own, member));
                (own.bytes, index as u32)
            })
            .collect();
        forms.sort();
        if let Some(order) = &mut self.order {
            order.lists.insert(NodePath(self.path.clone().into()), forms.iter().map(|(_, index)| *index).collect());
        }
        out.len(forms.len());
        for (bytes, _) in &forms {
            out.nested(bytes);
        }
    }

    /// Writes `columns` in the order of their labels' canonical positions,
    /// each name through `name`.
    fn columns(&self, out: &mut CanonicalWriter, columns: &[RelationColumn], name: impl Fn(&mut CanonicalWriter, &ColumnName)) {
        let mut ordered: Vec<(u32, &ColumnName)> = columns.iter().map(|c| (self.position(c.label), &c.name)).collect();
        ordered.sort_by_key(|(position, _)| *position);
        out.len(ordered.len());
        for (position, column) in ordered {
            name(out, column);
            out.int(position);
        }
    }

    /// Runs `write` with the labels of `scope`.
    fn in_scope(&mut self, scope: LabelScope, write: impl FnOnce(&mut Self)) {
        let labels = self.labeling(scope).0;
        self.with_labels(labels, write);
    }

    /// Runs `write` with `labels`, the labels of the scope whose form stands
    /// at the node being written, and records them.
    fn with_labels(&mut self, labels: Labels, write: impl FnOnce(&mut Self)) {
        if let Some(order) = &mut self.order {
            order.labels.insert(NodePath(self.path.clone().into()), by_position(&labels));
        }
        let outer = std::mem::replace(&mut self.labels, labels);
        write(self);
        self.labels = outer;
    }

    /// The canonical labeling of `scope`, and whether its search reached
    /// the cap.
    fn labeling(&mut self, scope: LabelScope) -> (Labels, bool) {
        let mut graph = GraphBuilder::new(self.names);
        let root = graph.vertex(Tag::Root, |_| {});
        scope.graph(&mut graph, root);
        let graph = graph.colored();
        let outer = std::mem::replace(&mut self.search.remaining, SEARCH_NODE_CAP);
        let mut best = None;
        let mut cut_short = false;
        let colors = graph.initial.clone();
        self.visit(&graph, colors, scope, &mut best, &mut cut_short);
        self.search.remaining = outer;
        self.search.reached |= cut_short;
        (best.expect("the search reaches a leaf").1, cut_short)
    }

    /// One node of the search: refines `colors`, then individualizes each
    /// label of the first largest cell of labels that is not a singleton, or,
    /// at a leaf, keeps the least form. Where the budget is spent, the search
    /// sets `cut_short` and goes on to its first leaf alone.
    fn visit(&mut self, graph: &ColoredGraph, mut colors: Vec<u32>, scope: LabelScope, best: &mut Option<(Vec<u8>, Labels)>, cut_short: &mut bool) {
        if self.search.remaining == 0 {
            *cut_short = true;
            if best.is_some() {
                return;
            }
        } else {
            self.search.remaining -= 1;
        }
        graph.refine(&mut colors);
        let Some(cell) = graph.target_cell(&colors) else {
            let labels = graph.leaf_labels(&colors);
            let order = self.order.take();
            let mut out = CanonicalWriter::default();
            self.with_labels(labels.clone(), |cx| scope.write(cx, &mut out));
            self.order = order;
            if best.as_ref().is_none_or(|(form, _)| out.bytes < *form) {
                *best = Some((out.bytes, labels));
            }
            return;
        };
        for vertex in cell {
            let mut split = colors.clone();
            let color = colors[vertex];
            for c in split.iter_mut() {
                if *c >= color {
                    *c += 1;
                }
            }
            split[vertex] = color;
            self.visit(graph, split, scope, best, cut_short);
            if *cut_short && best.is_some() {
                return;
            }
        }
    }
}

/// The graph of a scope, as [`canonical_labeling`] refines it: a vertex per
/// atom, colored by its relation and its negation; a vertex per label; a
/// vertex per `0`; a vertex per `OR`, branch, `IF` part, `ALL` part, `NOT`
/// group, constraint and head site; and edges labeled by their role, an
/// atom's edge to a label by its column path as the name writer writes it.
struct GraphBuilder<'n> {
    names: &'n dyn NameWriter,
    colors: Vec<Vec<u8>>,
    edges: Vec<(usize, usize, Vec<u8>)>,
    labels: StableHashMap<LabelId, usize>,
}

impl<'n> GraphBuilder<'n> {
    fn new(names: &'n dyn NameWriter) -> Self {
        GraphBuilder { names, colors: Vec::new(), edges: Vec::new(), labels: StableHashMap::default() }
    }

    fn vertex(&mut self, tag: Tag, color: impl FnOnce(&mut CanonicalWriter)) -> usize {
        let mut out = CanonicalWriter::default();
        out.tag(tag);
        color(&mut out);
        self.colors.push(out.bytes);
        self.colors.len() - 1
    }

    fn label(&mut self, label: LabelId) -> usize {
        if let Some(&vertex) = self.labels.get(&label) {
            return vertex;
        }
        let vertex = self.vertex(Tag::Label, |_| {});
        self.labels.insert(label, vertex);
        vertex
    }

    fn edge(&mut self, from: usize, to: usize, tag: Tag, label: impl FnOnce(&mut CanonicalWriter)) {
        let mut out = CanonicalWriter::default();
        out.tag(tag);
        label(&mut out);
        self.edges.push((from, to, out.bytes));
    }

    /// A vertex of `tag` under `parent`, by an edge of `role` and `index`.
    fn child(&mut self, parent: usize, role: Tag, index: usize, tag: Tag, color: impl FnOnce(&mut CanonicalWriter)) -> usize {
        let vertex = self.vertex(tag, color);
        self.edge(parent, vertex, role, |out| out.len(index));
        vertex
    }

    fn label_use(&mut self, from: usize, label: LabelUse, edge: impl FnOnce(&mut CanonicalWriter)) {
        let (to, mark) = match label {
            LabelUse::Fresh(id) => (self.label(id), Tag::Fresh),
            LabelUse::Join(id) => (self.label(id), Tag::Join),
            LabelUse::Key(id) => (self.label(id), Tag::Key),
            LabelUse::Zero => (self.vertex(Tag::Zero, |_| {}), Tag::Zero),
        };
        self.edge(from, to, mark, edge);
    }

    fn body(&mut self, body: &Body, parent: usize, role: Tag, index: usize) {
        let vertex = self.child(parent, role, index, Tag::Body, |_| {});
        for conjunct in body.conjuncts.iter() {
            self.conjunct(conjunct, vertex);
        }
    }

    fn conjunct(&mut self, conjunct: &Conjunct, body: usize) {
        match conjunct {
            Conjunct::Atom(atom) => self.atom(atom.value(), false, body, Tag::Member, 0),
            Conjunct::Not(Negated::Atom(atom)) => self.atom(atom.value(), true, body, Tag::Member, 0),
            Conjunct::Not(Negated::Form(form)) => {
                let vertex = self.child(body, Tag::Member, 0, Tag::NotForm, |_| {});
                self.conjunct(form, vertex);
            }
            Conjunct::Constraint(constraint) => {
                let vertex = self.child(body, Tag::Member, 0, Tag::Constraint, |out| out.byte(constraint.op as u8));
                let first = constraint.first;
                let to = self.label(first.label);
                self.edge(vertex, to, Tag::Part, |out| {
                    out.len(0);
                    out.flag(first.fresh);
                });
                match constraint.second {
                    Operand::Label(second) => {
                        let to = self.label(second.label);
                        self.edge(vertex, to, Tag::Part, |out| {
                            out.len(1);
                            out.flag(second.fresh);
                        });
                    }
                    Operand::Zero => {
                        let zero = self.vertex(Tag::Zero, |_| {});
                        self.edge(vertex, zero, Tag::Part, |out| out.len(1));
                    }
                }
            }
            Conjunct::Or(branches) => {
                let vertex = self.child(body, Tag::Member, 0, Tag::Or, |_| {});
                for branch in branches.iter() {
                    self.body(branch.value(), vertex, Tag::Branch, 0);
                }
            }
            Conjunct::If { test, then, otherwise } => {
                let vertex = self.child(body, Tag::Member, 0, Tag::If, |_| {});
                for (index, part) in [test, then, otherwise].into_iter().enumerate() {
                    self.body(part.value(), vertex, Tag::Part, index);
                }
            }
            Conjunct::All { domain, body: each } => {
                let vertex = self.child(body, Tag::Member, 0, Tag::All, |_| {});
                for (index, part) in [domain, each].into_iter().enumerate() {
                    self.body(part.value(), vertex, Tag::Part, index);
                }
            }
        }
    }

    fn atom(&mut self, atom: &Atom, negated: bool, parent: usize, role: Tag, index: usize) {
        let names = self.names;
        let vertex = self.child(parent, role, index, Tag::Atom, |out| {
            out.flag(negated);
            names.write_name(&atom.relation, out);
        });
        for site in atom.sites.iter() {
            self.site(vertex, site, &[], &|out, path| names.write_column(&atom.relation, path, out));
        }
    }

    /// The edges from `from` to the labels of `site`, each labeled by its
    /// column path as `column` writes it and its index among the site's
    /// arguments.
    fn site(&mut self, from: usize, site: &Site, prefix: &[ColumnName], column: &dyn Fn(&mut CanonicalWriter, &[ColumnName])) {
        let path: Vec<ColumnName> = prefix.iter().chain(std::iter::once(&site.column)).cloned().collect();
        for (index, arg) in site.value.args.iter().enumerate() {
            match arg {
                SiteArg::Label(label) => self.label_use(from, *label, |out| {
                    column(out, &path);
                    out.len(index);
                }),
                SiteArg::Field(field) => self.site(from, field, &path, column),
            }
        }
    }

    fn input(&mut self, input: &InstanceInput, parent: usize, index: usize) {
        let vertex = self.child(parent, Tag::Input, index, Tag::Input, |out| out.text(&input.name.0));
        for (index, site) in input.head.iter().enumerate() {
            let head = self.child(vertex, Tag::Head, index, Tag::Head, |_| {});
            self.site(head, site, &[], &|out, path| out.column_path(path));
        }
        self.body(input.body.value(), vertex, Tag::Body, 0);
    }

    fn key_body(&mut self, key: &KeyBody, parent: usize, role: Tag) {
        let vertex = self.child(parent, role, 0, Tag::KeyBody, |_| {});
        self.body(key.body.value(), vertex, Tag::Body, 0);
        self.columns(vertex, &key.columns, |out, name| out.column(name));
    }

    fn key_clause(&mut self, key: &KeyClause, parent: usize) {
        let vertex = self.child(parent, Tag::KeyClause, 0, Tag::KeyClause, |_| {});
        self.key_body(&key.key, vertex, Tag::Key);
        for (index, input) in key.inputs.iter().enumerate() {
            self.input(input.value(), vertex, index);
        }
    }

    /// Edges from `from` to the labels of `columns`, each labeled by its
    /// name as `name` writes it.
    fn columns(&mut self, from: usize, columns: &[RelationColumn], name: impl Fn(&mut CanonicalWriter, &ColumnName)) {
        for column in columns {
            let to = self.label(column.label);
            self.edge(from, to, Tag::Column, |out| name(out, &column.name));
        }
    }

    fn clause(&mut self, clause: &Clause, parent: usize, index: usize) {
        let names = self.names;
        let derives = relation_of(&clause.derives);
        let vertex = self.child(parent, Tag::Form, index, Tag::Clause, |out| out.byte(clause.keyword as u8));
        self.body(clause.body.value(), vertex, Tag::Body, 0);
        for (index, one) in clause.ones.iter().enumerate() {
            let mark = self.child(vertex, Tag::One, index, Tag::One, |_| {});
            for (index, label) in one.key.iter().enumerate() {
                let to = self.label(*label);
                self.edge(mark, to, Tag::Part, |out| out.len(index));
            }
        }
        self.columns(vertex, &clause.columns, |out, name| names.write_column(&derives, std::slice::from_ref(name), out));
    }

    fn instance(&mut self, instance: &Instance, parent: usize, index: usize) {
        let vertex = self.child(parent, Tag::Form, index, Tag::Instance, |_| {});
        if let Some(key) = &instance.key {
            self.key_clause(key.value(), vertex);
        }
        for (index, input) in instance.inputs.iter().enumerate() {
            self.input(input.value(), vertex, index);
        }
    }

    fn choose(&mut self, choose: &Choose, parent: usize, index: usize) {
        let names = self.names;
        let relation = RelationRef::Declared(choose.name.clone());
        let vertex = self.child(parent, Tag::Form, index, Tag::Choose, |out| out.flag(choose.from_inside_for));
        if let Some(rows) = &choose.rows {
            self.key_body(rows, vertex, Tag::Key);
        }
        self.columns(vertex, &choose.candidate_columns, |out, name| names.write_column(&relation, std::slice::from_ref(name), out));
        self.body(choose.from.value(), vertex, Tag::Body, 0);
        for (index, never) in choose.never.iter().enumerate() {
            self.body(never.value(), vertex, Tag::Part, index);
        }
    }

    fn rigid_det(&mut self, rigid: &RigidDet, parent: usize, index: usize) {
        let vertex = self.child(parent, Tag::Form, index, Tag::RigidDet, |_| {});
        if let Some(key) = &rigid.key {
            self.key_body(key, vertex, Tag::Key);
        }
        if let Some(instance) = &rigid.instance {
            self.key_body(instance, vertex, Tag::Instance);
        }
        for (index, part) in rigid.parts.iter().enumerate() {
            self.atom(part.value(), false, vertex, Tag::Part, index);
        }
    }

    fn demonstrated_key(&mut self, demonstrated: &Demonstrated, parent: usize) {
        if let Some(key) = &demonstrated.key {
            self.key_clause(key.value(), parent);
        }
        for (index, input) in demonstrated.inputs.iter().enumerate() {
            self.input(input.value(), parent, index);
        }
    }

    fn demo_rule(&mut self, rule: &DemoRule, parent: usize) {
        let names = self.names;
        let prediction = prediction();
        self.columns(parent, &rule.fields, |out, name| names.write_column(&prediction, std::slice::from_ref(name), out));
        for (index, form) in rule.forms.iter().enumerate() {
            match form {
                Form::Clause(clause) => self.clause(clause.value(), parent, index),
                Form::Instance(instance) => self.instance(instance.value(), parent, index),
                Form::Choose(choose) => self.choose(choose.value(), parent, index),
                Form::RigidDet(rigid) => self.rigid_det(rigid.value(), parent, index),
                // A form of a scope of its own reads no label of the rule.
                Form::Claim(_) | Form::Demonstrated(_) | Form::Alts(_) => {}
            }
        }
    }

    /// The graph as numbers: each vertex's initial color, as its rank among
    /// the colors, and each vertex's edges, by the rank of their labels.
    fn colored(self) -> ColoredGraph {
        let initial = ranks(&self.colors);
        let edge_labels: Vec<Vec<u8>> = self.edges.iter().map(|(_, _, label)| label.clone()).collect();
        let edge_ranks = ranks(&edge_labels);
        let mut edges = vec![Vec::new(); self.colors.len()];
        for ((from, to, _), rank) in self.edges.iter().zip(edge_ranks) {
            edges[*from].push((rank, false, *to));
            edges[*to].push((rank, true, *from));
        }
        let mut labels: Vec<(LabelId, usize)> = self.labels.into_iter().collect();
        labels.sort_by_key(|(_, vertex)| *vertex);
        ColoredGraph { initial, edges, labels }
    }
}

/// The rank of each value among the distinct values of `values`.
fn ranks<T: Ord + Clone>(values: &[T]) -> Vec<u32> {
    let mut distinct = values.to_vec();
    distinct.sort();
    distinct.dedup();
    values.iter().map(|v| distinct.binary_search(v).expect("a value of the list") as u32).collect()
}

/// A scope's graph as numbers, which the search refines.
struct ColoredGraph {
    initial: Vec<u32>,
    /// Each vertex's edges: the edge label's rank, whether the edge comes
    /// into the vertex, and the vertex at its other end.
    edges: Vec<Vec<(u32, bool, usize)>>,
    /// Each label and its vertex.
    labels: Vec<(LabelId, usize)>,
}

impl ColoredGraph {
    /// 1-dimensional Weisfeiler–Leman refinement of `colors`, to its fixed
    /// point. Each new color keeps the order of the old ones.
    fn refine(&self, colors: &mut Vec<u32>) {
        let mut count = colors.iter().max().map_or(0, |c| c + 1);
        loop {
            let signatures: Vec<(u32, Vec<(u32, bool, u32)>)> = (0..colors.len())
                .map(|vertex| {
                    let mut around: Vec<(u32, bool, u32)> =
                        self.edges[vertex].iter().map(|(label, inward, other)| (*label, *inward, colors[*other])).collect();
                    around.sort();
                    (colors[vertex], around)
                })
                .collect();
            *colors = ranks(&signatures);
            let refined = colors.iter().max().map_or(0, |c| c + 1);
            if refined == count {
                return;
            }
            count = refined;
        }
    }

    /// The vertices of the first largest cell of labels that is not a
    /// singleton, or `None` where each label has a color of its own.
    fn target_cell(&self, colors: &[u32]) -> Option<Vec<usize>> {
        let mut cells: std::collections::BTreeMap<u32, Vec<usize>> = std::collections::BTreeMap::new();
        for (_, vertex) in &self.labels {
            cells.entry(colors[*vertex]).or_default().push(*vertex);
        }
        let largest = cells.values().map(Vec::len).max().filter(|&size| size > 1)?;
        cells.into_values().find(|cell| cell.len() == largest)
    }

    /// The labels' positions at a leaf, in the order of their colors.
    fn leaf_labels(&self, colors: &[u32]) -> Labels {
        let mut ordered: Vec<(u32, LabelId)> = self.labels.iter().map(|(label, vertex)| (colors[*vertex], *label)).collect();
        ordered.sort_by_key(|(color, _)| *color);
        ordered.into_iter().enumerate().map(|(position, (_, label))| (label, position as u32)).collect()
    }
}

impl LabelScope<'_> {
    fn graph(self, graph: &mut GraphBuilder, root: usize) {
        match self {
            LabelScope::Clause(clause) => graph.clause(clause, root, 0),
            LabelScope::Instance(instance) => graph.instance(instance, root, 0),
            LabelScope::Choose(choose) => graph.choose(choose, root, 0),
            LabelScope::RigidDet(rigid) => graph.rigid_det(rigid, root, 0),
            LabelScope::DemonstratedKey(demonstrated) => graph.demonstrated_key(demonstrated, root),
            LabelScope::DemoRule(rule) => graph.demo_rule(rule, root),
            LabelScope::Body(body) => graph.body(body, root, Tag::Body, 0),
            LabelScope::Atom(atom) => graph.atom(atom, false, root, Tag::Part, 0),
            LabelScope::KeyClause(key) => graph.key_clause(key, root),
            LabelScope::InstanceInput(input) => graph.input(input, root, 0),
        }
    }

    /// Writes the part of the form that the scope's labels enter.
    fn write(self, cx: &mut Context, out: &mut CanonicalWriter) {
        match self {
            LabelScope::Clause(clause) => clause.write_form(cx, out),
            LabelScope::Instance(instance) => instance.write_form(cx, out),
            LabelScope::Choose(choose) => choose.write_form(cx, out),
            LabelScope::RigidDet(rigid) => rigid.write_form(cx, out),
            LabelScope::DemonstratedKey(demonstrated) => demonstrated_key(cx, out, demonstrated),
            LabelScope::DemoRule(rule) => rule.write_form(cx, out),
            LabelScope::Body(body) => body.write_form(cx, out),
            LabelScope::Atom(atom) => atom.write_form(cx, out),
            LabelScope::KeyClause(key) => key.write_form(cx, out),
            LabelScope::InstanceInput(input) => input.write_form(cx, out),
        }
    }
}

/// The relation a clause or a `param` form names, as an atom reads it.
fn relation_of(relation: &ProgramRelation) -> RelationRef {
    match relation {
        ProgramRelation::Declared(name) => RelationRef::Declared(name.clone()),
        ProgramRelation::Output(name) => RelationRef::Output(name.clone()),
    }
}

/// The scope of a form that stands in a program, a claim or an `ALT`, where
/// its own content holds labels.
fn form_scope(form: &Form) -> Option<LabelScope<'_>> {
    match form {
        Form::Claim(claim) => claim.value().scope(),
        Form::Clause(clause) => clause.value().scope(),
        Form::Instance(instance) => instance.value().scope(),
        Form::Choose(choose) => choose.value().scope(),
        Form::RigidDet(rigid) => rigid.value().scope(),
        Form::Demonstrated(demonstrated) => demonstrated.value().scope(),
        Form::Alts(alts) => alts.value().scope(),
    }
}

/// Writes a form that stands in a program, a claim or an `ALT`: a scope of
/// its own.
fn form_root(cx: &mut Context, out: &mut CanonicalWriter, form: &Form) {
    let labels = form_scope(form).map(|scope| cx.labeling(scope).0);
    form_with(cx, out, form, labels);
}

/// Writes `form` with `labels`, or with the labels of the scope it stands
/// in where `labels` is `None`.
fn form_with(cx: &mut Context, out: &mut CanonicalWriter, form: &Form, labels: Option<Labels>) {
    let mut write = |cx: &mut Context| match form {
        Form::Claim(claim) => claim.value().write_form(cx, out),
        Form::Clause(clause) => clause.value().write_form(cx, out),
        Form::Instance(instance) => instance.value().write_form(cx, out),
        Form::Choose(choose) => choose.value().write_form(cx, out),
        Form::RigidDet(rigid) => rigid.value().write_form(cx, out),
        Form::Demonstrated(demonstrated) => demonstrated.value().write_form(cx, out),
        Form::Alts(alts) => alts.value().write_form(cx, out),
    };
    match labels {
        Some(labels) => cx.with_labels(labels, write),
        None => write(cx),
    }
}

/// Writes the forms of a program, a claim or an `ALT`, each a scope of its
/// own.
fn forms_root(cx: &mut Context, out: &mut CanonicalWriter, forms: &[Form]) {
    out.len(forms.len());
    for (index, form) in forms.iter().enumerate() {
        cx.child(index, |cx| form_root(cx, out, form));
    }
}

fn demonstrated_key(cx: &mut Context, out: &mut CanonicalWriter, demonstrated: &Demonstrated) {
    out.option(demonstrated.key.as_ref(), |out, key| cx.child(0, |cx| key.value().write_form(cx, out)));
    let first = usize::from(demonstrated.key.is_some());
    out.len(demonstrated.inputs.len());
    for (index, input) in demonstrated.inputs.iter().enumerate() {
        cx.child(first + index, |cx| input.value().write_form(cx, out));
    }
}

fn label_use(cx: &Context, out: &mut CanonicalWriter, label: LabelUse) {
    match label {
        LabelUse::Fresh(id) => {
            out.tag(Tag::Fresh);
            cx.label(out, id);
        }
        LabelUse::Join(id) => {
            out.tag(Tag::Join);
            cx.label(out, id);
        }
        LabelUse::Key(id) => {
            out.tag(Tag::Key);
            cx.label(out, id);
        }
        LabelUse::Zero => out.tag(Tag::Zero),
    }
}

fn constraint_label(cx: &Context, out: &mut CanonicalWriter, label: ConstraintLabel) {
    out.flag(label.fresh);
    cx.label(out, label.label);
}

/// Writes `site`, with each column path as `column` writes it.
fn site(cx: &Context, out: &mut CanonicalWriter, site_: &Site, prefix: &[ColumnName], column: &dyn Fn(&mut CanonicalWriter, &[ColumnName])) {
    let path: Vec<ColumnName> = prefix.iter().chain(std::iter::once(&site_.column)).cloned().collect();
    out.tag(Tag::Site);
    column(out, &path);
    out.len(site_.value.args.len());
    for arg in site_.value.args.iter() {
        match arg {
            SiteArg::Label(label) => {
                out.tag(Tag::ArgLabel);
                label_use(cx, out, *label);
            }
            SiteArg::Field(field) => {
                out.tag(Tag::ArgField);
                site(cx, out, field, &path, column);
            }
        }
    }
}

/// Writes a key body, whose body is the child at `index` of the node being
/// written.
fn key_body(cx: &mut Context, out: &mut CanonicalWriter, key: &KeyBody, index: usize) {
    out.tag(Tag::KeyBody);
    cx.child(index, |cx| key.body.value().write_form(cx, out));
    cx.columns(out, &key.columns, |out, name| out.column(name));
}

fn data_value(out: &mut CanonicalWriter, value: &DataValue) {
    match value {
        DataValue::Integer(n) => {
            out.tag(Tag::Integer);
            out.write(&n.to_le_bytes());
        }
        DataValue::Orientation(name) => {
            out.tag(Tag::Orientation);
            out.text(name);
        }
        DataValue::List(values) => {
            out.tag(Tag::List);
            out.len(values.len());
            for value in values.iter() {
                data_value(out, value);
            }
        }
    }
}

fn grid(out: &mut CanonicalWriter, grid: &Grid) {
    out.len(grid.rows.len());
    for row in grid.rows.iter() {
        out.len(row.len());
        for cell in row.iter() {
            out.option(cell.as_ref(), data_value);
        }
    }
    out.option(grid.anchor, |out, anchor| {
        out.int(anchor.row);
        out.int(anchor.column);
    });
}

fn param_value(cx: &Context, out: &mut CanonicalWriter, value: &ParamValue) {
    match value {
        ParamValue::Rows(rows) => {
            out.tag(Tag::Rows);
            out.len(rows.len());
            for row in rows.iter() {
                out.len(row.len());
                for value in row.iter() {
                    data_value(out, value);
                }
            }
        }
        ParamValue::Grids(grids) => {
            out.tag(Tag::Grids);
            out.len(grids.len());
            for rows in grids.iter() {
                out.len(rows.before.len());
                for value in rows.before.iter() {
                    data_value(out, value);
                }
                grid(out, &rows.grid);
            }
        }
        ParamValue::Derivation { derivation, rows } => {
            out.tag(Tag::Derivation);
            cx.names.write_name(&RelationRef::Lib(derivation.clone()), out);
            out.len(rows.len());
            for row in rows.iter() {
                out.len(row.len());
                for field in row.iter() {
                    out.column(&field.column);
                    data_value(out, &field.value);
                }
            }
        }
    }
}

fn alts_names(out: &mut CanonicalWriter, names: &[AltsName]) {
    out.len(names.len());
    for name in names {
        out.text(&name.0);
    }
}

fn witnesses(cx: &Context, out: &mut CanonicalWriter, witnesses: &[Witness]) {
    out.len(witnesses.len());
    for witness in witnesses {
        out.text(&witness.id);
        out.byte(witness.plausibility as u8);
        match &witness.verdict {
            Verdict::Concept => out.tag(Tag::Concept),
            Verdict::Alt(name) => {
                out.tag(Tag::AltVerdict);
                out.text(&name.0);
            }
            Verdict::Any => out.tag(Tag::Any),
            Verdict::Other => out.tag(Tag::Other),
        }
        out.option(witness.body.as_ref(), |out, body| {
            out.len(body.relaxed.len());
            for slug in body.relaxed.iter() {
                out.text(&slug.0);
            }
            out.text(&body.separates.0);
            out.len(body.assigns.len());
            for (relation, value) in body.assigns.iter() {
                cx.names.write_name(&relation_of(relation), out);
                param_value(cx, out, value);
            }
            grid(out, &body.input);
            out.len(body.outputs.len());
            for output in body.outputs.iter() {
                out.len(output.names.len());
                for name in output.names.iter() {
                    out.len(name.len());
                    for case in name.iter() {
                        match case {
                            CaseRef::Concept => out.tag(Tag::Concept),
                            CaseRef::Alt(name) => {
                                out.tag(Tag::AltVerdict);
                                out.text(&name.0);
                            }
                        }
                    }
                }
                match &output.value {
                    OutputValue::Undefined => out.tag(Tag::Undefined),
                    OutputValue::Grids(grids) => {
                        out.tag(Tag::Grids);
                        out.len(grids.len());
                        for g in grids.iter() {
                            grid(out, g);
                        }
                    }
                }
            }
        });
    }
}

fn alt_record(cx: &Context, out: &mut CanonicalWriter, record: &AltRecord) {
    out.text(&record.name.0);
    witnesses(cx, out, &record.witnesses);
    out.len(record.nested.len());
    for nested in record.nested.iter() {
        alt_record(cx, out, nested);
    }
}

/// The form of a node kind, written with the labels the writer holds.
trait WriteForm {
    /// The scope of the labels the kind's own form holds, where the kind
    /// stands as a scope or as a node whose hash is taken apart from its
    /// scope.
    fn scope(&self) -> Option<LabelScope<'_>> {
        None
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter);
}

impl WriteForm for Demonstrated {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::DemonstratedKey(self))
    }

    /// Writes the form, with the key clause and the inputs under the labels
    /// the writer holds, and each `DEMO_RULE` form under its own.
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Demonstrated);
        out.declared(&self.name.0);
        demonstrated_key(cx, out, self);
        let first = usize::from(self.key.is_some()) + self.inputs.len();
        out.len(self.rules.len());
        for (index, rule) in self.rules.iter().enumerate() {
            let rule = rule.value();
            cx.child(first + index, |cx| cx.in_scope(LabelScope::DemoRule(rule), |cx| rule.write_form(cx, out)));
        }
    }
}

impl WriteForm for Program {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Program);
        forms_root(cx, out, &self.forms);
    }
}

impl WriteForm for Claim {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Claim);
        out.byte(self.kind as u8);
        out.text(&self.slug.0);
        out.text(&self.text.0);
        out.option(self.approximated.as_ref(), |out, text| out.text(&text.0));
        forms_root(cx, out, &self.forms);
    }
}

impl WriteForm for Clause {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Clause(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        let derives = relation_of(&self.derives);
        out.tag(Tag::Clause);
        out.byte(self.keyword as u8);
        cx.names.write_name(&derives, out);
        out.option(self.gloss.as_ref(), |out, text| out.text(&text.0));
        out.len(self.proposers.len());
        for proposer in self.proposers.iter() {
            cx.names.write_name(&RelationRef::Lib(proposer.clone()), out);
        }
        cx.child(0, |cx| self.body.value().write_form(cx, out));
        out.len(self.ones.len());
        for one in self.ones.iter() {
            out.len(one.key.len());
            for label in one.key.iter() {
                cx.label(out, *label);
            }
        }
        let names = cx.names;
        cx.columns(out, &self.columns, |out, name| names.write_column(&derives, std::slice::from_ref(name), out));
    }
}

impl WriteForm for Body {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Body(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Body);
        cx.sorted(out, &self.conjuncts, |cx, out, conjunct| write_conjunct(cx, out, conjunct));
    }
}

fn write_conjunct(cx: &mut Context, out: &mut CanonicalWriter, conjunct: &Conjunct) {
    match conjunct {
        Conjunct::Atom(atom) => {
            out.tag(Tag::Atom);
            atom.value().write_form(cx, out);
        }
        Conjunct::Not(Negated::Atom(atom)) => {
            out.tag(Tag::NotAtom);
            atom.value().write_form(cx, out);
        }
        Conjunct::Not(Negated::Form(form)) => {
            out.tag(Tag::NotForm);
            cx.child(0, |cx| write_conjunct(cx, out, form));
        }
        Conjunct::Constraint(constraint) => {
            out.tag(Tag::Constraint);
            out.byte(constraint.op as u8);
            constraint_label(cx, out, constraint.first);
            match constraint.second {
                Operand::Label(label) => {
                    out.tag(Tag::ArgLabel);
                    constraint_label(cx, out, label);
                }
                Operand::Zero => out.tag(Tag::Zero),
            }
        }
        Conjunct::Or(branches) => {
            out.tag(Tag::Or);
            cx.sorted(out, branches, |cx, out, branch| branch.value().write_form(cx, out));
        }
        Conjunct::If { test, then, otherwise } => {
            out.tag(Tag::If);
            for (index, part) in [test, then, otherwise].into_iter().enumerate() {
                cx.child(index, |cx| part.value().write_form(cx, out));
            }
        }
        Conjunct::All { domain, body } => {
            out.tag(Tag::All);
            for (index, part) in [domain, body].into_iter().enumerate() {
                cx.child(index, |cx| part.value().write_form(cx, out));
            }
        }
    }
}

impl WriteForm for Atom {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Atom(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        let names = cx.names;
        names.write_name(&self.relation, out);
        out.len(self.sites.len());
        for s in self.sites.iter() {
            site(cx, out, s, &[], &|out, path| names.write_column(&self.relation, path, out));
        }
    }
}

impl WriteForm for Instance {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Instance(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Instance);
        out.declared(&self.name.0);
        cx.names.write_name(&RelationRef::Lib(self.component.clone()), out);
        out.option(self.key.as_ref(), |out, key| cx.child(0, |cx| key.value().write_form(cx, out)));
        let first = usize::from(self.key.is_some());
        out.len(self.inputs.len());
        for (index, input) in self.inputs.iter().enumerate() {
            cx.child(first + index, |cx| input.value().write_form(cx, out));
        }
    }
}

impl WriteForm for KeyClause {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::KeyClause(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::KeyClause);
        key_body(cx, out, &self.key, 0);
        out.len(self.inputs.len());
        for (index, input) in self.inputs.iter().enumerate() {
            cx.child(1 + index, |cx| input.value().write_form(cx, out));
        }
    }
}

impl WriteForm for InstanceInput {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::InstanceInput(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Input);
        out.text(&self.name.0);
        out.len(self.head.len());
        for head in self.head.iter() {
            site(cx, out, head, &[], &|out, path| out.column_path(path));
        }
        cx.child(self.head.len(), |cx| self.body.value().write_form(cx, out));
    }
}

impl WriteForm for Choose {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Choose(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Choose);
        out.declared(&self.name.0);
        out.option(self.rows.as_ref(), |out, rows| key_body(cx, out, rows, 0));
        let relation = RelationRef::Declared(self.name.clone());
        let names = cx.names;
        cx.columns(out, &self.candidate_columns, |out, name| names.write_column(&relation, std::slice::from_ref(name), out));
        let first = usize::from(self.rows.is_some());
        cx.child(first, |cx| self.from.value().write_form(cx, out));
        out.flag(self.from_inside_for);
        out.len(self.never.len());
        for (index, never) in self.never.iter().enumerate() {
            cx.child(first + 1 + index, |cx| never.value().write_form(cx, out));
        }
    }
}

impl WriteForm for RigidDet {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::RigidDet(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::RigidDet);
        out.declared(&self.name.0);
        out.option(self.key.as_ref(), |out, key| key_body(cx, out, key, 0));
        let instance_index = usize::from(self.key.is_some());
        out.option(self.instance.as_ref(), |out, instance| key_body(cx, out, instance, instance_index));
        out.len(self.parts.len());
        for part in self.parts.iter() {
            part.value().write_form(cx, out);
        }
    }
}

impl WriteForm for DemoRule {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::DemoRule(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::DemoRule);
        out.text(&self.name.0);
        let names = cx.names;
        let prediction = prediction();
        cx.columns(out, &self.fields, |out, name| names.write_column(&prediction, std::slice::from_ref(name), out));
        out.option(self.text.as_ref(), |out, text| out.text(&text.0));
        out.len(self.forms.len());
        for (index, form) in self.forms.iter().enumerate() {
            cx.child(index, |cx| match form {
                Form::Clause(_) | Form::Instance(_) | Form::Choose(_) | Form::RigidDet(_) => form_with(cx, out, form, None),
                Form::Claim(_) | Form::Demonstrated(_) | Form::Alts(_) => form_root(cx, out, form),
            });
        }
    }
}

impl WriteForm for Alts {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Alts);
        out.text(&self.name.0);
        out.text(&self.gloss.0);
        out.text(&self.concept.0);
        out.len(self.alts.len());
        for (index, alt) in self.alts.iter().enumerate() {
            cx.child(index, |cx| alt.value().write_form(cx, out));
        }
    }
}

impl WriteForm for Alt {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Alt);
        out.text(&self.name.0);
        out.len(self.items.len());
        for (index, item) in self.items.iter().enumerate() {
            cx.child(index, |cx| match item {
                AltItem::Form(form) => {
                    out.tag(Tag::AltForm);
                    form_root(cx, out, form);
                }
                AltItem::Alt(alt) => {
                    out.tag(Tag::AltNested);
                    alt.value().write_form(cx, out);
                }
            });
        }
    }
}

impl WriteForm for Param {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Param);
        cx.names.write_name(&relation_of(&self.name), out);
        out.len(self.columns.len());
        for column in self.columns.iter() {
            out.byte(*column as u8);
        }
        param_value(cx, out, &self.value);
    }
}

impl WriteForm for Arcdata {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Arcdata);
        out.option(self.representative.as_ref(), |out, representative| {
            out.text(&representative.task_id);
            out.option(representative.case.as_ref(), |out, names| alts_names(out, names));
        });
        out.len(self.params.len());
        for param in self.params.iter() {
            param.value().write_form(cx, out);
        }
        out.len(self.excludes.len());
        for exclude in self.excludes.iter() {
            alts_names(out, &exclude.combination);
            out.option(exclude.reason.as_ref(), |out, text| out.text(&text.0));
        }
        out.len(self.witness_records.len());
        for record in self.witness_records.iter() {
            match record {
                WitnessRecord::Alts { name, alts } => {
                    out.tag(Tag::AltsRecord);
                    out.text(&name.0);
                    out.len(alts.len());
                    for alt in alts.iter() {
                        alt_record(cx, out, alt);
                    }
                }
                WitnessRecord::Approximated { claim, witnesses: list } => {
                    out.tag(Tag::ApproximatedRecord);
                    out.text(&claim.0);
                    witnesses(cx, out, list);
                }
            }
        }
    }
}

impl<T: WriteForm> Canonical for T {
    fn write_canonical(&self, out: &mut CanonicalWriter, search: &mut SearchBudget, names: &dyn NameWriter) {
        let mut cx = Context::new(search, names);
        if let Some(scope) = self.scope() {
            cx.labels = cx.labeling(scope).0;
        }
        self.write_form(&mut cx, out);
    }

    fn canonical_eq(&self, other: &Self) -> bool {
        form_of(self).0.bytes == form_of(other).0.bytes
    }
}
