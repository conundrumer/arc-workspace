//! The names of a case program after resolution, and the resolved content
//! they write: the [`NameWriter`] of the resolver.

use std::sync::Arc;

use super::columns::{Columns, Place};
use super::GraphNodeIndex;
use crate::hash::StableHashMap;
use crate::program::canonical::{AsWritten, Canonical, CanonicalForm, CanonicalWriter, NameWriter, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    Body, ColumnName, DeclaredName, Demonstrated, NameScope, Node, OutputOwner, Program, RelationRef,
};

/// Writes the path of the output that `relation` reads, after the
/// content of the node it resolves to, which tells apart the outputs of
/// one node.
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
    out.len(parts.len());
    for part in &parts {
        out.len(part.len());
        out.write(part);
    }
    out.write(tail);
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
}

impl Names {
    /// The target of `relation` read in `scope`: its declaration in
    /// `scope`, or in the program's.
    pub(super) fn find(&self, scope: &NameScope, relation: &RelationRef) -> Option<&Target> {
        let in_scope = |scope: &NameScope| self.scopes.get(scope).and_then(|names| names.get(relation));
        in_scope(scope).or_else(|| in_scope(&NameScope::Program))
    }

    /// The columns of `relation` read in `scope`, where they are known.
    pub(super) fn columns(&self, scope: &NameScope, relation: &RelationRef) -> Option<&Columns> {
        if let RelationRef::Lib(_) = relation {
            return self.lib.get(relation);
        }
        let target = self.find(scope, relation)?;
        match &target.columns {
            ColumnsOf::Fixed(columns) => Some(columns),
            ColumnsOf::OfNode => self.node_columns.get(target.node.0 as usize)?.as_ref(),
        }
    }

    /// The resolved content of the node at `path` of `program`.
    pub(super) fn content(&self, program: &Node<Program>, path: &NodePath) -> Option<CanonicalForm> {
        if path.0.is_empty() {
            let forms: Option<Vec<Arc<[u8]>>> = (0..program.value().forms.len())
                .map(|index| self.content(program, &NodePath(Box::new([crate::program::path::PathStep(index as u32)]))).map(|form| form.bytes))
                .collect();
            return Some(combined(0, forms?, &[]));
        }
        if let Some(form) = self.fixed.get(path) {
            return Some(form.clone());
        }
        let mut node = NodeRef::Program(program.value());
        let mut scope = NameScope::Program;
        let mut own = None;
        let mut atom = None;
        for (depth, step) in path.0.iter().enumerate() {
            node = *node.children().get(step.0 as usize)?;
            match node {
                NodeRef::DemoRule(_) => scope = NameScope::DemoRule(NodePath(path.0[..=depth].into())),
                NodeRef::Conjunct(crate::program::Conjunct::Atom(found) | crate::program::Conjunct::Not(crate::program::Negated::Atom(found))) => {
                    atom = Some(found.value())
                }
                NodeRef::Atom(found) => atom = Some(found),
                _ => {}
            }
            own = Own::of(node).or(own);
        }
        let writer = Writer { names: self, scope: &scope, own: own.as_ref() };
        written(node, path, atom, &writer)
    }
}

/// The canonical form of `node`, at `path`, through `writer`. A site or a
/// bare label is written as the atom `atom` that holds it, with that site
/// alone.
pub(super) fn written(node: NodeRef<'_>, path: &NodePath, atom: Option<&crate::program::Atom>, writer: &Writer<'_>) -> Option<CanonicalForm> {
    if let NodeRef::Demonstrated(demonstrated) = node {
        return Some(demonstrated_form(demonstrated, path, writer));
    }
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
            match target.map(|target| &self.names.contents[target.node.0 as usize]) {
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
