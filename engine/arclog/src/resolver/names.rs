//! The names of a case program after resolution, and the resolved content
//! they write: the [`NameWriter`] of the resolver.

use std::sync::Arc;

use super::columns::{ColumnOrders, Columns, Place};
use super::{DependencyKind, GraphNodeIndex};
use crate::hash::StableHashMap;
use crate::program::canonical::{
    cached_write, canonical_labeling, AsWritten, Canonical, CanonicalForm, CanonicalOrder, CanonicalWriter, LabelScope, LabelingBound, NameWriter, SearchBudget,
};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{
    Body, Clause, ColumnName, DeclaredName, DemoRule, DemoRuleName, Demonstrated, Form, InstanceName, LabelId, NameScope, Node, OutputOwner, Program, RelationRef,
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

/// The content bytes of the form at `path` of `program`, a form of a node
/// in `scope`, as [`Names::form_content`] gives them.
pub(super) fn form_bytes(names: &Names, program: &Program, scope: &NameScope, path: &NodePath) -> Arc<[u8]> {
    let form = node_at(NodeRef::Program(program), path).expect("the path of a form of the case");
    let own = Own::of(form);
    let writer = Writer { names, scope, own: own.as_ref() };
    names.form_content(program, form, path, None, &writer).expect("a form has a canonical form").bytes
}

/// The content of a node of kind `kind` whose forms have the content bytes
/// `parts`, in any order.
pub(super) fn node_form(kind: &DependencyKind, parts: impl IntoIterator<Item = Arc<[u8]>>) -> crate::program::canonical::CanonicalForm {
    let mut tail = CanonicalWriter::default();
    match kind {
        DependencyKind::Fact(fact) => AsWritten.write_name(&RelationRef::Fact(*fact), &mut tail),
        DependencyKind::InstanceInput { input: port, .. } | DependencyKind::InstanceOutput { output: port, .. } => tail.port_step(port),
        _ => {}
    }
    combined(kind_tag(kind), parts, &tail.finish().bytes)
}

/// The tag of each kind of node in its content.
fn kind_tag(kind: &DependencyKind) -> u8 {
    match kind {
        DependencyKind::Fact(_) => 1,
        DependencyKind::Clause(_) => 2,
        DependencyKind::InstanceInput { .. } => 3,
        DependencyKind::InstanceOutput { .. } => 4,
        DependencyKind::Parameter(_) => 5,
        DependencyKind::Chosen(_) => 6,
        DependencyKind::RigidAssembly(_) => 7,
        DependencyKind::Demonstrated(_) => 8,
        DependencyKind::RecursiveInstance(_) => 9,
        DependencyKind::Out(_) => 10,
    }
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
    /// The relation that a part of a `RIGID_DET` form reads, in the path of
    /// an output of that form.
    PartRead,
    /// A field of the `key` record of an `INIT` form's output, by the rank of
    /// its label in the labeling of the form.
    KeyRank,
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
    /// The orders of the columns of each node, as `node_columns`, under
    /// which its content is the same.
    pub(super) node_orders: Vec<ColumnOrders>,
    pub(super) lib: StableHashMap<RelationRef, Columns>,
    /// The content of each form that resolves in the concept program,
    /// as [`super::ConceptReads`] gives, by its path.
    pub(super) fixed: StableHashMap<NodePath, CanonicalForm>,
    /// The columns that the relation of each clause keeps, by the
    /// clause's path, where they differ, in count or in order, from the
    /// clause's columns in their canonical positions, as [`super::build`] gives them from the reads of the node.
    pub(super) kept: StableHashMap<NodePath, Columns>,
    /// The resolution of the forms before the last, where these names are
    /// those of the last form alone, as [`super::resolve_last`] gives them:
    /// `contents` and `node_columns` then hold the nodes after those of
    /// `earlier`, and a lookup that finds nothing here is made there.
    pub(super) earlier: Option<Arc<super::ResolvedProgram>>,
    /// For each node of these names that no pass of its resolution reads,
    /// the slot of its content, written on its first read by
    /// [`super::ResolvedProgram::node_content`]; its entry of `contents`
    /// is then empty.
    pub(super) unwritten: Vec<Option<std::sync::OnceLock<CanonicalForm>>>,
    /// For each `INIT` form with a key clause, by the scope that declares it
    /// and its name, the rank of each field of its `key` record: the position
    /// of the field's label in the canonical labeling of the form, so that
    /// the order in which the key writes its columns is not in the content of
    /// a read of a field. Written by [`super::Builder::contents`] when it
    /// reaches the form's first node.
    pub(super) key_ranks: StableHashMap<NameScope, StableHashMap<InstanceName, Box<[(ColumnName, u32)]>>>,
    /// For each `INIT` form with a key clause, as in `key_ranks`, the rank
    /// of each field of its `key` record in the form's own content: the
    /// position of the field's label in the canonical labeling of the key's
    /// body. A read of the form's own output stands in the labeling that
    /// gives `key_ranks`, and the key's body reads no output of its form, so
    /// this rank is known while that labeling is made.
    pub(super) own_key_ranks: StableHashMap<NameScope, StableHashMap<InstanceName, Box<[(ColumnName, u32)]>>>,
    /// Whether the content is written with the order of the named sites and
    /// head sites outside it, as [`NameWriter::feature_sites`] says.
    pub(super) feature_sites: bool,
    /// Set when a search for a canonical labeling under a [`Writer`] of these
    /// names passed [`crate::program::canonical::SEARCH_NODE_CAP`]: the
    /// content that these names write is then not free of the written order.
    pub(super) labeling_bound: Arc<std::sync::atomic::AtomicBool>,
}

impl Names {
    /// The bound that a search for a canonical labeling under these names, or
    /// under the names of the forms before the last, passed.
    pub(super) fn labeling_bound(&self) -> Option<LabelingBound> {
        let reached = self.labeling_bound.load(std::sync::atomic::Ordering::Relaxed)
            || self.earlier.as_ref().is_some_and(|earlier| earlier.names.labeling_bound().is_some());
        reached.then(LabelingBound::at_cap)
    }

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

    /// The content of `node`, `Some(None)` where it is not yet written. A
    /// node of the earlier layers that left its content unwritten gets it
    /// here ([`super::ResolvedProgram::node_content`]).
    pub(super) fn node_content(&self, node: usize) -> Option<Option<&CanonicalForm>> {
        match &self.earlier {
            Some(earlier) if node < self.first_node() => earlier.written_content(node),
            _ => self.contents.get(node - self.first_node()).map(Option::as_ref),
        }
    }

    /// Whether the content of `node` is left for its first read.
    pub(super) fn is_unwritten(&self, node: usize) -> bool {
        match &self.earlier {
            Some(earlier) if node < self.first_node() => earlier.names.is_unwritten(node),
            _ => self.unwritten.get(node - self.first_node()).is_some_and(Option::is_some),
        }
    }

    /// The rank of the field `field` of the `key` record of the `INIT` form
    /// `instance`, read in `scope`: found in the scope that declares the form,
    /// as [`Names::find`] finds a name.
    pub(super) fn key_rank(&self, scope: &NameScope, instance: &InstanceName, field: &ColumnName) -> Option<u32> {
        let ranks = self.key_ranks_in(scope, instance).or_else(|| self.key_ranks_in(&NameScope::Program, instance))?;
        ranks.iter().find(|(name, _)| name == field).map(|(_, rank)| *rank)
    }

    pub(super) fn key_ranks_in(&self, scope: &NameScope, instance: &InstanceName) -> Option<&[(ColumnName, u32)]> {
        let own = self.key_ranks.get(scope).and_then(|ranks| ranks.get(instance));
        match own {
            Some(ranks) => Some(ranks),
            None => self.earlier.as_ref()?.names.key_ranks_in(scope, instance),
        }
    }

    /// The rank of the field `field` of the `key` record of the `INIT` form
    /// `instance` in the form's own content, read in `scope`, as
    /// [`Names::key_rank`] finds a rank.
    pub(super) fn own_key_rank(&self, scope: &NameScope, instance: &InstanceName, field: &ColumnName) -> Option<u32> {
        let ranks = self.own_key_ranks_in(scope, instance).or_else(|| self.own_key_ranks_in(&NameScope::Program, instance))?;
        ranks.iter().find(|(name, _)| name == field).map(|(_, rank)| *rank)
    }

    pub(super) fn own_key_ranks_in(&self, scope: &NameScope, instance: &InstanceName) -> Option<&[(ColumnName, u32)]> {
        let own = self.own_key_ranks.get(scope).and_then(|ranks| ranks.get(instance));
        match own {
            Some(ranks) => Some(ranks),
            None => self.earlier.as_ref()?.names.own_key_ranks_in(scope, instance),
        }
    }

    /// The columns of `node`, where they are known.
    pub(super) fn node_columns_of(&self, node: usize) -> Option<&Columns> {
        match &self.earlier {
            Some(earlier) if node < self.first_node() => earlier.names.node_columns_of(node),
            _ => self.node_columns.get(node - self.first_node())?.as_ref(),
        }
    }

    /// The orders of the columns of `node` under which its content is the
    /// same, none where they are not known.
    pub(super) fn node_orders_of(&self, node: usize) -> &[Box<[u16]>] {
        match &self.earlier {
            Some(earlier) if node < self.first_node() => earlier.names.node_orders_of(node),
            _ => self.node_orders.get(node - self.first_node()).map_or(&[], |orders| orders),
        }
    }

    /// The orders of the columns of `relation` read in `scope` under which
    /// its content is the same, as [`Names::columns`] gives the columns.
    pub(super) fn column_orders(&self, scope: &NameScope, relation: &RelationRef) -> &[Box<[u16]>] {
        match self.find(scope, relation) {
            Some(Target { node, columns: ColumnsOf::OfNode }) => self.node_orders_of(node.0 as usize),
            _ => &[],
        }
    }

    /// The columns a name of any scope declares for `node` as fixed, as for
    /// an output of an instance, which has no columns of its own node.
    pub(super) fn fixed_columns_of(&self, node: usize) -> Option<&Columns> {
        let own = self.scopes.values().flat_map(|names| names.values()).find_map(|target| match &target.columns {
            ColumnsOf::Fixed(columns) if target.node.0 as usize == node => Some(columns),
            _ => None,
        });
        own.or_else(|| self.earlier.as_ref()?.names.fixed_columns_of(node))
    }

    /// The columns that the relation of the clause at `path` keeps.
    pub(super) fn kept_at(&self, path: &NodePath) -> Option<&Columns> {
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

    /// The canonical order of the top-level form at `path` of `program`
    /// through the resolver's writer, and the form it writes (the form of
    /// [`Names::form_content`] before any kept columns). A `DEMONSTRATED`
    /// form has no order, as a path that names no top-level form has none.
    pub(super) fn order(&self, program: &Node<Program>, path: &NodePath) -> Option<(CanonicalOrder, CanonicalForm)> {
        let [top] = &path.0[..] else { return None };
        let form = program.value().forms.get(top.0 as usize)?;
        if matches!(form, Form::Demonstrated(_)) {
            return None;
        }
        let at = At::of(program, path)?;
        let writer = Writer { names: self, scope: &at.scope, own: at.own.as_ref() };
        Some(CanonicalOrder::with_names(form, &writer, &mut SearchBudget::new()))
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

    /// For each part of the `RIGID_DET` form at `path` of `program`, the
    /// least index of a part whose swap with it leaves the form's canonical
    /// form through the resolver as it is, its own index where none does.
    /// Ties are a class: the swaps that leave a form as it is make a group.
    /// `None` where `path` names no `RIGID_DET` form.
    pub(super) fn part_positions(&self, program: &Node<Program>, path: &NodePath) -> Option<Box<[u32]>> {
        let at = At::of(program, path)?;
        let NodeRef::RigidDet(rigid) = at.node else { return None };
        let writer = Writer { names: self, scope: &at.scope, own: at.own.as_ref() };
        let form = |parts: Vec<Node<crate::program::Atom>>| {
            let swapped = crate::program::RigidDet { parts: parts.into(), ..rigid.clone() };
            written_through(NodeRef::RigidDet(&swapped), None, &writer).map(|form| form.bytes)
        };
        let written = form(rigid.parts.to_vec())?;
        let mut positions: Vec<u32> = (0..rigid.parts.len() as u32).collect();
        for later in 0..rigid.parts.len() {
            // A part that ties with one part of a class ties with the least part of it, so only the least of each class is tried.
            for first in (0..later).filter(|first| positions[*first] == *first as u32) {
                let mut parts = rigid.parts.to_vec();
                parts.swap(first, later);
                if form(parts).is_some_and(|swapped| swapped == written) {
                    positions[later] = first as u32;
                    break;
                }
            }
        }
        Some(positions.into())
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
/// alone. A `DEMO_RULE` form is written as [`rule_content`] gives it.
pub(super) fn written(node: NodeRef<'_>, path: &NodePath, atom: Option<&crate::program::Atom>, writer: &Writer<'_>) -> Option<CanonicalForm> {
    match node {
        NodeRef::Demonstrated(demonstrated) => Some(demonstrated_form(demonstrated, path, writer)),
        NodeRef::DemoRule(rule) => written_through(NodeRef::DemoRule(&rule_content(rule, writer)), atom, writer),
        _ => written_through(node, atom, writer),
    }
}

/// The `DEMO_RULE` form `rule` as its content holds it: with no name, which
/// a decode gives by the rule's place among the rules of its form, and with
/// its forms in the order of [`rule_form_order`], so that two rules that
/// list their forms in two orders that follow what each form reads have
/// one content.
fn rule_content(rule: &DemoRule, writer: &Writer<'_>) -> DemoRule {
    let forms = rule_form_order(rule, writer).into_iter().map(|at| (rule.forms[at].clone(), rule.forms.from_alt(at))).collect();
    DemoRule { name: DemoRuleName(Box::from("")), forms, ..rule.clone() }
}

/// The indexes of the forms of `rule` in the order of its content: at each
/// step, among the forms left that read no relation that a form left
/// declares, or among all the forms left where none is ready, as on a
/// cycle, the form whose canonical form through `writer`, taken alone, is
/// least. A form that reads another comes after it, and two forms of which
/// neither reads the other come in the order of their contents. Forms of
/// one content keep their order.
fn rule_form_order(rule: &DemoRule, writer: &Writer<'_>) -> Vec<usize> {
    let forms = &rule.forms[..];
    let keys: Vec<Option<Arc<[u8]>>> = forms.iter().map(|form| written_through(NodeRef::from(form), None, writer).map(|form| form.bytes)).collect();
    let declared: Vec<Option<&DeclaredName>> = forms.iter().map(declared_name).collect();
    let reads: Vec<Vec<usize>> = forms
        .iter()
        .enumerate()
        .map(|(at, form)| {
            let mut names = Vec::new();
            names_read(NodeRef::from(form), &mut names);
            let reads_form = |other: usize| other != at && declared[other].is_some_and(|name| declared[at] != Some(name) && names.contains(&name));
            (0..forms.len()).filter(|&other| reads_form(other)).collect()
        })
        .collect();
    let mut placed = vec![false; forms.len()];
    let mut order = Vec::with_capacity(forms.len());
    while order.len() < forms.len() {
        let left: Vec<usize> = (0..forms.len()).filter(|&at| !placed[at]).collect();
        let ready: Vec<usize> = left.iter().copied().filter(|&at| reads[at].iter().all(|&read| placed[read])).collect();
        let pool = if ready.is_empty() { left } else { ready };
        let next = pool.into_iter().min_by(|&a, &b| keys[a].cmp(&keys[b])).expect("a form is left");
        placed[next] = true;
        order.push(next);
    }
    order
}

/// The name of the relation that `form` declares, or of the owner of the
/// outputs it declares; none for a form that declares none.
fn declared_name(form: &Form) -> Option<&DeclaredName> {
    use crate::program::ProgramRelation;
    match form {
        Form::Clause(clause) => Some(match &clause.value().derives {
            ProgramRelation::Declared(name) => &name.0,
            ProgramRelation::Output(output) => owner_name(&output.of),
        }),
        Form::Instance(instance) => Some(&instance.value().name.0),
        Form::Choose(choose) => Some(&choose.value().name.0),
        Form::RigidDet(rigid) => Some(&rigid.value().name.0),
        Form::Demonstrated(demonstrated) => Some(&demonstrated.value().name.0),
        Form::Claim(_) | Form::Alts(_) | Form::Out(_) => None,
    }
}

/// The name of the owner of the outputs that `owner` names.
fn owner_name(owner: &OutputOwner) -> &DeclaredName {
    match owner {
        OutputOwner::Instance(instance) => &instance.0,
        OutputOwner::RigidDet(rigid) => &rigid.0,
    }
}

/// Adds to `names` the name of the relation, or of the owner of the output,
/// that each atom below `node` reads.
fn names_read<'n>(node: NodeRef<'n>, names: &mut Vec<&'n DeclaredName>) {
    if let Some(atom) = node.atom() {
        match &atom.relation {
            RelationRef::Declared(name) => names.push(&name.0),
            RelationRef::Output(output) => names.push(owner_name(&output.of)),
            RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => {}
        }
    }
    for child in node.children() {
        names_read(child, names);
    }
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
        NodeRef::Out(value) => value.write_canonical(out_, search, writer),
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
/// `path`: its key clause and its inputs through `writer`, then its
/// `DEMO_RULE` forms, each through a writer of the rule's scope, so that
/// each name a rule declares is written as the resolved content of what
/// it resolves to in that rule. The rules are a set: their forms stand
/// sorted, so that the order of the rules is not in the content.
fn demonstrated_form(demonstrated: &Demonstrated, path: &NodePath, writer: &Writer<'_>) -> CanonicalForm {
    let mut out = CanonicalWriter::default();
    let bare = Demonstrated { rules: Arc::from([]), ..demonstrated.clone() };
    bare.write_canonical(&mut out, &mut SearchBudget::new(), writer);
    let mut rules: Vec<Arc<[u8]>> = super::demo_rules(demonstrated, path)
        .map(|(rule_path, rule)| {
            let scope = NameScope::DemoRule(rule_path.clone());
            let rule_writer = Writer { names: writer.names, scope: &scope, own: None };
            written(NodeRef::DemoRule(rule), &rule_path, None, &rule_writer).expect("a rule has a canonical form").bytes
        })
        .collect();
    rules.sort();
    out.len(rules.len());
    for form in &rules {
        out.len(form.len());
        out.write(form);
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

    /// The path of `column`, a column of `relation`, an output of the form
    /// being written, as its content writes it. A file names a field of a
    /// type parameter's record by its written name and a decode by a slot,
    /// so the path holds no name of a label or a field:
    /// - A label that stands alone at a site on a column of a type
    ///   parameter that holds no record, as `(:t B)` where the form binds
    ///   `t` to one label, adds its name to the site's path
    ///   ([`crate::program::SiteArg::NamedLabel`]). The column is the site's
    ///   own column whatever the name, so the path stops at that column.
    /// - A site on a field of a type parameter's record, as `(:t (:O O2))`
    ///   where the form binds `t` to a record, names the field by its place
    ///   among the record's fields, the slot a decode gives it.
    /// - A site on a field of the `key` record, as `(:key Ko)`, names the
    ///   field by its rank in the form's own content
    ///   ([`Names::own_key_rank`]), so that the order in which the key
    ///   writes its columns is not in the content either.
    fn own_column<'c>(&self, relation: &RelationRef, column: &'c [ColumnName]) -> std::borrow::Cow<'c, [ColumnName]> {
        use std::borrow::Cow;
        let slot = |slot: u32| Cow::Owned(vec![column[0].clone(), ColumnName::Slot(slot)]);
        match self.names.columns(self.scope, relation).and_then(|columns| columns.place(column)) {
            Some(Place::Column(_)) => Cow::Borrowed(&column[..1]),
            Some(Place::Field(position, group)) => match self.instance_key_field(relation, column) {
                None => slot(u32::from(position.0 - group.start.0)),
                Some((instance, field)) => match self.names.own_key_rank(self.scope, instance, field) {
                    Some(rank) => slot(rank),
                    // The ranks are made from the key's body alone, before any other labeling of the form, so only
                    // a read in that body finds none.
                    None => Cow::Borrowed(column),
                },
            },
            _ => Cow::Borrowed(column),
        }
    }

    /// The `INIT` form and the field, where `column` is `[key, field]` of an
    /// output of an `INIT` form that `relation` names.
    fn instance_key_field<'c>(&self, relation: &'c RelationRef, column: &'c [ColumnName]) -> Option<(&'c InstanceName, &'c ColumnName)> {
        let RelationRef::Output(output) = relation else { return None };
        let OutputOwner::Instance(instance) = &output.of else { return None };
        let [record, field] = column else { return None };
        (*record == super::columns::key()).then_some((instance, field))
    }

    /// Whether the node that `relation` resolves to has no content yet, and
    /// is not left for its first read.
    fn unwritten_target(&self, relation: &RelationRef) -> bool {
        let Some(target) = self.names.find(self.scope, relation) else { return false };
        let node = target.node.0 as usize;
        matches!(self.names.node_content(node), Some(None)) && !self.names.is_unwritten(node)
    }

    /// Writes the path of the output that `relation` reads, other than the
    /// content of its node. The first step of a `RIGID_DET` output's path
    /// that names a part stands for the relation the part reads, and is
    /// written as the content of that relation, since the name the part has
    /// is a slot in a decode and a spelling in a file.
    fn write_path(&self, relation: &RelationRef, out: &mut CanonicalWriter) {
        use crate::program::{InstanceName, OutputName, OutputStep, RelationName, RigidDetName};
        let RelationRef::Output(output) = relation else { return };
        let (OutputOwner::RigidDet(_), [OutputStep::Part(owner), rest @ ..]) = (&output.of, &output.path[..]) else {
            return write_output_path(out, relation);
        };
        let read = if rest.is_empty() {
            RelationRef::Declared(RelationName(owner.clone()))
        } else {
            let of = |of| RelationRef::Output(OutputName { of, path: rest.into() });
            let instance = of(OutputOwner::Instance(InstanceName(owner.clone())));
            if self.names.find(self.scope, &instance).is_some() { instance } else { of(OutputOwner::RigidDet(RigidDetName(owner.clone()))) }
        };
        out.write(&[Mark::PartRead as u8]);
        self.write_name(&read, out);
    }
}

impl NameWriter for Writer<'_> {
    fn feature_sites(&self) -> bool {
        self.names.feature_sites
    }

    fn labeling_bound_reached(&self) {
        self.names.labeling_bound.store(true, std::sync::atomic::Ordering::Relaxed);
    }

    fn write_name(&self, relation: &RelationRef, out: &mut CanonicalWriter) {
        if self.own(relation).is_some() {
            out.write(&[Mark::Own as u8]);
        } else {
            let target = match relation {
                RelationRef::Declared(_) | RelationRef::Output(_) => self.names.find(self.scope, relation),
                RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => None,
            };
            let node = target.map(|target| target.node.0 as usize);
            match node.map(|node| self.names.node_content(node).expect("a content slot for each node")) {
                Some(Some(content)) => {
                    out.write(&[Mark::Content as u8]);
                    out.write(&content.hash.0.to_le_bytes());
                }
                Some(None) => {
                    debug_assert!(node.is_some_and(|node| !self.names.is_unwritten(node)), "a write reads the content of a node left unwritten");
                    out.write(&[Mark::Open as u8]);
                    return AsWritten.write_name(relation, out);
                }
                None => {
                    out.write(&[Mark::Written as u8]);
                    return AsWritten.write_name(relation, out);
                }
            }
        }
        self.write_path(relation, out);
    }

    /// Writes a mark that holds no name, so that the resolved content of a
    /// form holds no name of its own, as that of a clause holds no name of
    /// the relation it derives.
    fn write_own(&self, _name: &DeclaredName, out: &mut CanonicalWriter) {
        out.write(&[Mark::Own as u8]);
    }

    fn write_column(&self, relation: &RelationRef, column: &[ColumnName], out: &mut CanonicalWriter) {
        self.write_column_in(relation, column, 0, out);
    }

    /// The orders of the node's columns, none for the form's own relation,
    /// whose orders its labeling gives.
    fn column_orders(&self, relation: &RelationRef) -> usize {
        if self.own(relation).is_some() {
            return 0;
        }
        self.names.column_orders(self.scope, relation).len()
    }

    /// Writes a column of the form's own relation by a mark that no
    /// labeling sets, since the labeling gives that column's position.
    fn write_column_in(&self, relation: &RelationRef, column: &[ColumnName], order: usize, out: &mut CanonicalWriter) {
        match self.own(relation) {
            Some(Own::Relation(_)) => return out.write(&[Mark::Own as u8]),
            Some(Own::Owner(_)) => {
                out.write(&[Mark::Own as u8]);
                return AsWritten.write_column(relation, &self.own_column(relation, column), out);
            }
            None => {}
        }
        match self.names.columns(self.scope, relation).and_then(|columns| columns.place(column)) {
            Some(Place::Field(position, _)) => match self.instance_key_field(relation, column) {
                Some((instance, field)) => match self.names.key_rank(self.scope, instance, field) {
                    Some(rank) => {
                        out.write(&[Mark::KeyRank as u8]);
                        out.write(&rank.to_le_bytes());
                    }
                    None => {
                        // A key field is ranked once its `INIT` form's content is reached, and a read comes after the
                        // content of the node it resolves to, so only a read on a cycle, which the cycle check refuses,
                        // comes first. The field then stands as written, which no order of the key's columns changes.
                        debug_assert!(self.unwritten_target(relation), "a key field is read before its `INIT` form is ranked, off a cycle");
                        out.write(&[Mark::Written as u8]);
                        AsWritten.write_column(relation, column, out);
                    }
                },
                None => {
                    out.write(&[Mark::Position as u8]);
                    out.write(&position.0.to_le_bytes());
                }
            },
            Some(Place::Column(position)) => {
                // A kept write of another resolution can ask for an order that the relation lacks here: the position
                // then stands as it is, and that write's count of the orders differs.
                let orders = self.names.column_orders(self.scope, relation);
                let position = order.checked_sub(1).and_then(|order| orders.get(order)?.get(usize::from(position.0)).copied()).unwrap_or(position.0);
                out.write(&[Mark::Position as u8]);
                out.write(&position.to_le_bytes());
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
