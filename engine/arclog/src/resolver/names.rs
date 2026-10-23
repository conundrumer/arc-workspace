//! The names of a case program after resolution, and the resolved content
//! they write: the [`NameWriter`] of the resolver.

use std::sync::Arc;

use super::columns::{Columns, Place};
use super::GraphNodeIndex;
use crate::hash::StableHashMap;
use crate::program::canonical::{
    cached_write, canonical_labeling, AsWritten, Canonical, CanonicalForm, CanonicalWriter, LabelScope, NameWriter, SearchBudget,
};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    Body, Clause, ColumnName, DeclaredName, Demonstrated, Form, LabelId, NameScope, Node, OutputOwner, Program, RelationRef,
};

/// Writes the path of the output that `relation` reads, after the
/// content of the node it resolves to.
pub(super) fn write_output_path(out: &mut CanonicalWriter, relation: &RelationRef) {
    if let RelationRef::Output(output) = relation {
        out.output_path(&output.path);
    }
}

/// The form of `parts` sorted, after the mark `kind` and before `tail`,
/// so the content of a node of several forms has no order.
pub(super) fn combined(kind: u8, parts: impl IntoIterator<Item = Arc<[u8]>>, tail: &[u8]) -> CanonicalForm {
    let mut parts: Vec<Arc<[u8]>> = parts.into_iter().collect();
    parts.sort();
    let mut out = CanonicalWriter::default();
    out.write(&[kind]);
    write_parts(&mut out, &parts);
    out.write(tail);
    out.finish()
}

/// Writes the count of `parts`, then each part after its length.
fn write_parts(out: &mut CanonicalWriter, parts: &[Arc<[u8]>]) {
    out.len(parts.len());
    for part in parts {
        out.len(part.len());
        out.write(part);
    }
}

/// The form `form` followed by the names of `columns` in their order,
/// each part written as [`write_parts`] writes it.
fn with_columns(form: &CanonicalForm, columns: &Columns) -> CanonicalForm {
    let names = columns.names().map(|name| {
        let mut out = CanonicalWriter::default();
        out.name(name);
        out.finish().bytes
    });
    let parts: Vec<Arc<[u8]>> = std::iter::once(form.bytes.clone()).chain(names).collect();
    let mut out = CanonicalWriter::default();
    write_parts(&mut out, &parts);
    out.finish()
}

/// The mark of each kind of name or column a resolved content writes.
#[derive(Clone, Copy)]
#[repr(u8)]
enum Mark {
    /// The relation the form being written declares, or one of its
    /// columns.
    Own,
    /// A name as the file writes it: a fact, a lib name, or a name that
    /// resolves to no node.
    Written,
    /// The resolved content of a node.
    Content,
    /// A node whose content is not yet written, on a cycle.
    Open,
    Position,
    Group,
    /// The content of a part of a clause's body.
    Part,
}

/// The relation that the form being written declares: a relation, or the
/// owner of the outputs of an `INIT` or a `RIGID_DET` form.
#[derive(Clone, PartialEq, Eq, Debug)]
pub(super) enum Own {
    Relation(RelationRef),
    Owner(OutputOwner),
}

impl Own {
    /// The relation that the form at `node` declares.
    pub(super) fn of(node: NodeRef<'_>) -> Option<Own> {
        use crate::program::{InstanceName, ProgramRelation, RelationName, RigidDetName};
        let declared = |name: &RelationName| Own::Relation(RelationRef::Declared(name.clone()));
        match node {
            NodeRef::Clause(clause) => Some(Own::Relation(match &clause.derives {
                ProgramRelation::Declared(name) => RelationRef::Declared(name.clone()),
                ProgramRelation::Output(name) => RelationRef::Output(name.clone()),
            })),
            NodeRef::Choose(choose) => Some(declared(&choose.name)),
            NodeRef::Demonstrated(demonstrated) => Some(declared(&demonstrated.name)),
            NodeRef::Instance(instance) => Some(Own::Owner(OutputOwner::Instance(InstanceName::clone(&instance.name)))),
            NodeRef::RigidDet(rigid) => Some(Own::Owner(OutputOwner::RigidDet(RigidDetName::clone(&rigid.name)))),
            _ => None,
        }
    }

    fn holds(&self, relation: &RelationRef) -> bool {
        match self {
            Own::Relation(own) => own == relation,
            Own::Owner(owner) => matches!(relation, RelationRef::Output(output) if output.of == *owner),
        }
    }
}

/// What a relation name resolves to in one scope: its node, and its
/// columns, where they are known before the node's content.
#[derive(Clone, Debug)]
pub(super) struct Target {
    pub(super) node: GraphNodeIndex,
    pub(super) columns: ColumnsOf,
}

#[derive(Clone, Debug)]
pub(super) enum ColumnsOf {
    Fixed(Columns),
    /// The columns of the clause or the `CHOOSE` form of the node, in
    /// the canonical positions of their labels.
    OfNode,
}

/// The names of a case program after resolution: what each name of each
/// scope resolves to, the content and the columns of each node, and the
/// columns of each lib name and each input's default rows the program
/// reads.
#[derive(Clone, Debug, Default)]
pub(super) struct Names {
    pub(super) scopes: StableHashMap<NameScope, StableHashMap<RelationRef, Target>>,
    pub(super) contents: Vec<Option<CanonicalForm>>,
    pub(super) node_columns: Vec<Option<Columns>>,
    pub(super) lib: StableHashMap<RelationRef, Columns>,
    /// The content of each form that resolves in the concept program,
    /// as [`super::ConceptReads`] gives, by its path.
    pub(super) fixed: StableHashMap<NodePath, CanonicalForm>,
    /// The columns that the relation of each clause keeps, by the
    /// clause's path, where its node keeps fewer columns than the clause
    /// gives, as [`super::build`] gives them from the reads of the node.
    pub(super) kept: StableHashMap<NodePath, Columns>,
    /// The resolution of the forms before the last, where these names are
    /// those of the last form alone, as [`super::resolve_last`] gives them:
    /// `contents` and `node_columns` then hold the nodes after those of
    /// `earlier`, and a lookup that finds nothing here is made there.
    pub(super) earlier: Option<Arc<super::ResolvedProgram>>,
}

impl Names {
    /// The target of `relation` read in `scope`: its declaration in
    /// `scope`, or in the program's.
    pub(super) fn find(&self, scope: &NameScope, relation: &RelationRef) -> Option<&Target> {
        self.declared_in(scope, relation).or_else(|| self.declared_in(&NameScope::Program, relation))
    }

    /// The target of `relation` declared in `scope` alone.
    fn declared_in(&self, scope: &NameScope, relation: &RelationRef) -> Option<&Target> {
        let own = self.scopes.get(scope).and_then(|names| names.get(relation));
        own.or_else(|| self.earlier.as_ref()?.names.declared_in(scope, relation))
    }

    /// The count of the nodes of the earlier forms' resolution.
    pub(super) fn first_node(&self) -> usize {
        self.earlier.as_ref().map_or(0, |earlier| earlier.graph.nodes.len())
    }

    /// The content of `node`, `Some(None)` where it is not yet written.
    pub(super) fn node_content(&self, node: usize) -> Option<&Option<CanonicalForm>> {
        match &self.earlier {
            Some(earlier) if node < self.first_node() => earlier.names.node_content(node),
            _ => self.contents.get(node - self.first_node()),
        }
    }

    /// The columns of `node`, where they are known.
    pub(super) fn node_columns_of(&self, node: usize) -> Option<&Columns> {
        match &self.earlier {
            Some(earlier) if node < self.first_node() => earlier.names.node_columns_of(node),
            _ => self.node_columns.get(node - self.first_node())?.as_ref(),
        }
    }

    /// The columns that the relation of the clause at `path` keeps.
    fn kept_at(&self, path: &NodePath) -> Option<&Columns> {
        self.kept.get(path).or_else(|| self.earlier.as_ref()?.names.kept_at(path))
    }

    /// The columns of `relation` read in `scope`, where they are known.
    pub(super) fn columns(&self, scope: &NameScope, relation: &RelationRef) -> Option<&Columns> {
        if let RelationRef::Lib(_) = relation {
            return self.lib.get(relation).or_else(|| self.earlier.as_ref()?.names.columns(scope, relation));
        }
        let target = self.find(scope, relation)?;
        match &target.columns {
            ColumnsOf::Fixed(columns) => Some(columns),
            ColumnsOf::OfNode => self.node_columns_of(target.node.0 as usize),
        }
    }

    /// The resolved content of the node at `path` of `program`, that of a
    /// form as [`Names::form_content`] gives it.
    pub(super) fn content(&self, program: &Node<Program>, path: &NodePath) -> Option<CanonicalForm> {
        if path.0.is_empty() {
            let forms: Option<Vec<Arc<[u8]>>> = (0..program.value().forms.len())
                .map(|index| self.content(program, &NodePath::top(index as u32)).map(|form| form.bytes))
                .collect();
            return Some(combined(0, forms?, &[]));
        }
        let at = At::of(program, path)?;
        let writer = Writer { names: self, scope: &at.scope, own: at.own.as_ref() };
        self.form_content(program.value(), at.node, path, at.atom, &writer)
    }

    /// The content of the part of the body of the clause at `clause` of
    /// `program` that the conjuncts at `conjuncts`, indexes into the body,
    /// make, whose relation's columns are those of the clause whose labels
    /// `columns` gives: the resolved content of a clause of those conjuncts
    /// and those columns alone, after a mark that no form's content opens
    /// with, and `columns` in the order of the part's columns, the order of
    /// their labels' canonical positions. `None` where `clause` is the path
    /// of no clause.
    pub(super) fn part_content(&self, program: &Node<Program>, clause: &NodePath, conjuncts: &[u32], columns: &[LabelId]) -> Option<(CanonicalForm, Box<[LabelId]>)> {
        let at = At::of(program, clause)?;
        let NodeRef::Clause(whole) = at.node else { return None };
        let body = whole.body.value();
        let part = Clause {
            gloss: None,
            proposers: Arc::from([]),
            body: Node::new(Body { conjuncts: conjuncts.iter().map(|&index| body.conjuncts[index as usize].clone()).collect() }),
            ones: Arc::from([]),
            set: false,
            columns: whole.columns.iter().filter(|column| columns.contains(&column.label)).cloned().collect(),
            ..whole.clone()
        };
        let own = Own::of(NodeRef::Clause(&part));
        let writer = Writer { names: self, scope: &at.scope, own: own.as_ref() };
        let labeling = canonical_labeling(LabelScope::Clause(&part), &writer, &mut SearchBudget::new());
        let position = |label: &LabelId| labeling.positions.iter().find(|(found, _)| found == label).map(|(_, position)| *position);
        let mut ordered: Vec<LabelId> = columns.to_vec();
        ordered.sort_by_key(position);
        let form = written_through(NodeRef::Clause(&part), None, &writer).expect("a clause has a canonical form");
        let mut out = CanonicalWriter::default();
        out.write(&[Mark::Part as u8]);
        out.write(&form.bytes);
        Some((out.finish(), ordered.into()))
    }

    /// The resolved content of `node`, at `path` of `program`, through
    /// `writer`: its form in [`Names::fixed`], or else its form as
    /// [`written_at`] gives it, followed by the columns that
    /// [`Names::kept`] gives at `path`, where it gives them.
    pub(super) fn form_content(&self, program: &Program, node: NodeRef<'_>, path: &NodePath, atom: Option<&crate::program::Atom>, writer: &Writer<'_>) -> Option<CanonicalForm> {
        let form = match self.fixed.get(path) {
            Some(form) => form.clone(),
            None => written_at(program, node, path, atom, writer)?,
        };
        Some(match self.kept_at(path) {
            Some(columns) => with_columns(&form, columns),
            None => form,
        })
    }
}

/// The node at a path of a program, with the scope its names resolve in,
/// the relation the form that holds it declares, and the atom that holds
/// it.
struct At<'p> {
    node: NodeRef<'p>,
    scope: NameScope,
    own: Option<Own>,
    atom: Option<&'p crate::program::Atom>,
}

impl<'p> At<'p> {
    /// The node at `path` of `program`, or `None` where `path` names no
    /// node.
    fn of(program: &'p Node<Program>, path: &NodePath) -> Option<Self> {
        let mut at = At { node: NodeRef::Program(program.value()), scope: NameScope::Program, own: None, atom: None };
        for (depth, step) in path.0.iter().enumerate() {
            at.node = *at.node.children().get(step.0 as usize)?;
            if let NodeRef::DemoRule(_) = at.node {
                at.scope = NameScope::DemoRule(NodePath(path.0[..=depth].into()));
            }
            at.atom = at.node.atom().or(at.atom);
            at.own = Own::of(at.node).or(at.own);
        }
        Some(at)
    }
}

/// The canonical form of `node`, at `path` of `program`, through `writer`,
/// as [`written`] gives it, kept on the form's node through
/// [`cached_write`] where `node` is a top-level form other than a
/// `DEMONSTRATED` form, whose write reads names through `writer` alone.
pub(super) fn written_at(program: &Program, node: NodeRef<'_>, path: &NodePath, atom: Option<&crate::program::Atom>, writer: &Writer<'_>) -> Option<CanonicalForm> {
    let form = match &path.0[..] {
        [top] => program.forms.get(top.0 as usize),
        _ => None,
    };
    match form {
        Some(form) if !matches!(form, Form::Demonstrated(_)) => Some(cached_write(form, writer, |names| written_through(node, atom, names).expect("a form has a canonical form"))),
        _ => written(node, path, atom, writer),
    }
}

/// The canonical form of `node`, at `path`, through `writer`. A site or a
/// bare label is written as the atom `atom` that holds it, with that site
/// alone.
pub(super) fn written(node: NodeRef<'_>, path: &NodePath, atom: Option<&crate::program::Atom>, writer: &Writer<'_>) -> Option<CanonicalForm> {
    if let NodeRef::Demonstrated(demonstrated) = node {
        return Some(demonstrated_form(demonstrated, path, writer));
    }
    written_through(node, atom, writer)
}

/// The canonical form of `node`, a node other than a `DEMONSTRATED` form,
/// through `writer`, as [`written`] gives it.
fn written_through(node: NodeRef<'_>, atom: Option<&crate::program::Atom>, writer: &dyn NameWriter) -> Option<CanonicalForm> {
    let mut out = CanonicalWriter::default();
    let search = &mut SearchBudget::new();
    let out_ = &mut out;
    match node {
        NodeRef::Program(value) => value.write_canonical(out_, search, writer),
        NodeRef::Claim(value) => value.write_canonical(out_, search, writer),
        NodeRef::Clause(value) => value.write_canonical(out_, search, writer),
        NodeRef::Instance(value) => value.write_canonical(out_, search, writer),
        NodeRef::KeyClause(value) => value.write_canonical(out_, search, writer),
        NodeRef::InstanceInput(value) => value.write_canonical(out_, search, writer),
        NodeRef::Choose(value) => value.write_canonical(out_, search, writer),
        NodeRef::RigidDet(value) => value.write_canonical(out_, search, writer),
        NodeRef::Demonstrated(_) => unreachable!("a `DEMONSTRATED` form is written by `demonstrated_form`"),
        NodeRef::DemoRule(value) => value.write_canonical(out_, search, writer),
        NodeRef::Alts(value) => value.write_canonical(out_, search, writer),
        NodeRef::Alt(value) => value.write_canonical(out_, search, writer),
        NodeRef::Body(value) => value.write_canonical(out_, search, writer),
        NodeRef::Atom(value) => value.write_canonical(out_, search, writer),
        NodeRef::Conjunct(conjunct) => Body { conjuncts: Arc::from([conjunct.clone()]) }.write_canonical(out_, search, writer),
        NodeRef::Site(_) | NodeRef::Label(_) => {
            let atom = atom?;
            let site = match node {
                NodeRef::Site(site) => site.clone(),
                _ => atom.sites.iter().find(|site| site.value.args.iter().any(|arg| holds_label(node, arg)))?.clone(),
            };
            crate::program::Atom { relation: atom.relation.clone(), sites: Arc::from([site]) }.write_canonical(out_, search, writer)
        }
    }
    Some(out.finish())
}

/// The canonical form of the `DEMONSTRATED` form `demonstrated` at
/// `path`: its key clause and its inputs through `writer`, then each of
/// its `DEMO_RULE` forms through a writer of the rule's scope, so that
/// each name a rule declares is written as the resolved content of what
/// it resolves to in that rule.
fn demonstrated_form(demonstrated: &Demonstrated, path: &NodePath, writer: &Writer<'_>) -> CanonicalForm {
    let mut out = CanonicalWriter::default();
    let bare = Demonstrated { rules: Arc::from([]), ..demonstrated.clone() };
    bare.write_canonical(&mut out, &mut SearchBudget::new(), writer);
    out.len(demonstrated.rules.len());
    for (rule_path, rule) in super::demo_rules(demonstrated, path) {
        let scope = NameScope::DemoRule(rule_path.clone());
        let rule_writer = Writer { names: writer.names, scope: &scope, own: None };
        let form = written(NodeRef::DemoRule(rule), &rule_path, None, &rule_writer).expect("a rule has a canonical form");
        out.len(form.bytes.len());
        out.write(&form.bytes);
    }
    out.finish()
}

/// Whether `arg` is the bare label at `node`.
fn holds_label(node: NodeRef<'_>, arg: &crate::program::SiteArg) -> bool {
    use crate::program::SiteArg;
    match (node, arg) {
        (NodeRef::Label(found), SiteArg::Label(label) | SiteArg::NamedLabel { label, .. }) => std::ptr::eq(found, label),
        _ => false,
    }
}

/// The resolver's name writer: each name a node reads as the resolved
/// content of what it resolves to in `scope`, and each column a read
/// names as its position.
pub(super) struct Writer<'n> {
    pub(super) names: &'n Names,
    pub(super) scope: &'n NameScope,
    pub(super) own: Option<&'n Own>,
}

impl Writer<'_> {
    fn own(&self, relation: &RelationRef) -> Option<&Own> {
        self.own.filter(|own| own.holds(relation))
    }
}

impl NameWriter for Writer<'_> {
    fn write_name(&self, relation: &RelationRef, out: &mut CanonicalWriter) {
        if self.own(relation).is_some() {
            out.write(&[Mark::Own as u8]);
        } else {
            let target = match relation {
                RelationRef::Declared(_) | RelationRef::Output(_) => self.names.find(self.scope, relation),
                RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => None,
            };
            match target.map(|target| self.names.node_content(target.node.0 as usize).expect("a content slot for each node")) {
                Some(Some(content)) => {
                    out.write(&[Mark::Content as u8]);
                    out.write(&content.hash.0.to_le_bytes());
                }
                Some(None) => {
                    out.write(&[Mark::Open as u8]);
                    return AsWritten.write_name(relation, out);
                }
                None => {
                    out.write(&[Mark::Written as u8]);
                    return AsWritten.write_name(relation, out);
                }
            }
        }
        write_output_path(out, relation);
    }

    /// Writes a mark that holds no name, so that the resolved content of a
    /// form holds no name of its own, as that of a clause holds no name of
    /// the relation it derives.
    fn write_own(&self, _name: &DeclaredName, out: &mut CanonicalWriter) {
        out.write(&[Mark::Own as u8]);
    }

    /// Writes a column of the form's own relation by a mark that no
    /// labeling sets, since the labeling gives that column's position.
    fn write_column(&self, relation: &RelationRef, column: &[ColumnName], out: &mut CanonicalWriter) {
        match self.own(relation) {
            Some(Own::Relation(_)) => return out.write(&[Mark::Own as u8]),
            Some(Own::Owner(_)) => {
                out.write(&[Mark::Own as u8]);
                return AsWritten.write_column(relation, column, out);
            }
            None => {}
        }
        match self.names.columns(self.scope, relation).and_then(|columns| columns.place(column)) {
            Some(Place::Column(position) | Place::Field(position, _)) => {
                out.write(&[Mark::Position as u8]);
                out.write(&position.0.to_le_bytes());
            }
            Some(Place::Group(group)) => {
                out.write(&[Mark::Group as u8]);
                out.write(&group.start.0.to_le_bytes());
                out.write(&group.len.to_le_bytes());
            }
            None => {
                out.write(&[Mark::Written as u8]);
                AsWritten.write_column(relation, column, out);
            }
        }
    }
}
