//! Name resolution of a case program, and the dependency graph it gives,
//! and the resolution of each case of a solver. A relation that no block of
//! the case derives resolves to an undefined relation.
//!
//! The registry and resolver stage writes the bodies.

use std::sync::Arc;

use crate::diagnostic::WithDiagnostics;
use crate::hash::StableHash;
use crate::program::path::NodePath;
use crate::program::{
    ColumnName, InstanceName, LabelId, Node, OutputStep, PortName, RelationRef, Program, ProgramRelation, RelationName, RigidDetName,
};
use crate::registry::{LibName, Registry};

/// A node of the dependency graph: its kind and the name scope of its
/// declaration, so that two relations of one name that two `DEMO_RULE`
/// forms declare are two nodes.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct DependencyNode {
    pub kind: DependencyKind,
    pub scope: crate::program::NameScope,
}

/// The kind of a node of the dependency graph: a fact relation, a clause
/// relation, an instance input or output, a parameter, a chosen relation, a
/// `RIGID_DET` assembly or a `DEMONSTRATED` relation.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DependencyKind {
    Fact(crate::program::FactRelation),
    /// A relation a clause derives, an instance relation on a `RULE_OR_DET`
    /// line included.
    Clause(ProgramRelation),
    /// An input of an instance. The node reads the input's clause in its
    /// `INIT` form, or, where the case holds a `DET` of
    /// `&<instance>.<input>`, that `DET`'s [`DependencyKind::Parameter`]
    /// node, as `docs/arclog/arclog.md#the-alts-form` gives.
    InstanceInput { instance: InstanceName, input: PortName },
    /// An output of an instance. Where the case holds a `DET` of
    /// `&<instance>.<output>`, each read of that relation resolves to the
    /// `DET`'s [`DependencyKind::Parameter`] node, and none to this node, as
    /// `docs/arclog/arclog.md#the-alts-form` gives.
    InstanceOutput { instance: InstanceName, output: PortName },
    /// A parameter: a `DET` relation with no `ONE` mark, read as one node and
    /// never through its body, as a `DET` of the concept program is read in
    /// each case, with the values that `DET` keeps for it. A parameter that
    /// several blocks of the case determine is one node, with the values
    /// `docs/arclog/arclog.md#the-alts-form` gives it. Each read of the
    /// parameter's own `DET` bodies is an edge into the node, so a `DET` that
    /// reads a relation which depends on its own parameter makes a cycle.
    /// For a `DET` of a port of an instance, `&<instance>.<port>`, each read
    /// of the relation resolves to this node, and on an input the input's
    /// [`DependencyKind::InstanceInput`] node reads it, as
    /// `docs/arclog/arclog.md#the-alts-form` gives.
    Parameter(ProgramRelation),
    /// A chosen relation: a `CHOOSE` form's, or a clause's with `ONE` marks,
    /// a `DET` with `(ONE)` included, which is a chosen relation at the task
    /// level. An open parameter, a `DET` that ends in `(ONE)`, that several
    /// blocks of the case determine is one node, as a
    /// [`DependencyKind::Parameter`] is.
    Chosen(RelationName),
    /// A `RIGID_DET` form: one node for its assemblies
    /// (`docs/arclog/rigid.md#form`).
    RigidAssembly(RigidDetName),
    /// A `DEMONSTRATED` relation.
    Demonstrated(RelationName),
    /// An instance of a component with inputs that read its outputs, as
    /// `Unfold`'s `step`, `skip` and `take` do, with those inputs and its
    /// outputs: one node. The registry marks those inputs,
    /// [`crate::registry::InputPort::reads_outputs`], so the resolver names
    /// no component.
    RecursiveInstance(InstanceName),
}

/// The side of a node of the dependency graph, as
/// `docs/arclog/arclog.md#program` and `docs/arclog/arclog.md#instance` give:
/// per input, as a `RULE` relation is, or task-wide, as a `DET` relation is.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Side {
    PerInput,
    TaskWide,
}

/// The index of a node in a [`DependencyGraph`].
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct GraphNodeIndex(pub u32);

/// The dependency graph of a case program: each read is an edge from the
/// node read to the node that reads it.
#[derive(Clone, Debug, Default)]
pub struct DependencyGraph {
    pub nodes: Box<[DependencyNode]>,
    /// For each node, the nodes it reads.
    pub reads: Box<[Box<[GraphNodeIndex]>]>,
}

impl DependencyGraph {
    /// A cycle of the graph, as the nodes on it, or `None` where the graph is
    /// acyclic.
    pub fn find_cycle(&self) -> Option<Vec<GraphNodeIndex>> {
        const NEW: u8 = 0;
        const OPEN: u8 = 1;
        const CLOSED: u8 = 2;
        let mut state = vec![NEW; self.nodes.len()];
        for root in 0..self.nodes.len() {
            if state[root] != NEW {
                continue;
            }
            state[root] = OPEN;
            let mut stack: Vec<(usize, usize)> = vec![(root, 0)];
            while let Some(&(node, next)) = stack.last() {
                let Some(&GraphNodeIndex(read)) = self.reads[node].get(next) else {
                    state[node] = CLOSED;
                    stack.pop();
                    continue;
                };
                stack.last_mut().expect("the stack holds `node`").1 += 1;
                let read = read as usize;
                match state[read] {
                    NEW => {
                        state[read] = OPEN;
                        stack.push((read, 0));
                    }
                    OPEN => {
                        let start = stack.iter().position(|&(open, _)| open == read).expect("an open node stands on the stack");
                        let mut cycle: Vec<GraphNodeIndex> = stack[start..].iter().map(|&(n, _)| GraphNodeIndex(n as u32)).collect();
                        cycle.sort_by_key(|index| index.0);
                        return Some(cycle);
                    }
                    _ => {}
                }
            }
        }
        None
    }
}

/// What a name read in a case program resolves to.
#[derive(Clone, Debug)]
pub enum Resolution {
    /// A node of the case program's dependency graph.
    Node(GraphNodeIndex),
    /// A name of the lib.
    Lib(LibName),
    /// A relation that no block of the case derives: the case is undefined
    /// on each input where a clause reads it.
    Undefined(ProgramRelation),
    /// A name that resolves to nothing and is no relation a block could
    /// derive: a scope error, which the resolver reports.
    Unresolved,
}

/// A column of a derived relation, resolved to its canonical position: the
/// position of its label in the canonical labeling of the clause, as
/// [`crate::program::canonical::CanonicalLabeling`] gives it. The resolver
/// turns each column name that a read gives into its position.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ColumnPosition(pub u16);

/// The signature of a name a form reads: the canonical form of what the
/// name resolves to, its columns and their types. It compares as a key of
/// canonical parts does ([`crate::program`]).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Signature(pub crate::program::canonical::CanonicalForm);

/// The resolved content of a node of a case program: its canonical form,
/// with each name it reads standing for the resolved content of what it
/// resolves to. Two contents are equal when their hashes match and then
/// their canonical forms do, whatever file or decode they came from.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct ResolvedContent {
    form: crate::program::canonical::CanonicalForm,
}

impl ResolvedContent {
    /// The hash of the content's canonical form.
    pub fn content_hash(&self) -> StableHash {
        self.form.hash
    }
}

/// A case program after name resolution.
#[derive(Clone, Debug)]
pub struct ResolvedProgram {
    pub program: Node<Program>,
    pub graph: DependencyGraph,
    /// The paths of the forms of each node of the graph, by its index.
    forms: Box<[Box<[NodePath]>]>,
    /// The nodes of the graph that each form gives, by the form's path, in
    /// the order of their indices.
    form_nodes: crate::hash::StableHashMap<NodePath, Box<[GraphNodeIndex]>>,
    /// The side of each node of the graph, by its index.
    sides: Box<[Side]>,
    /// The side of each form whose reads the resolver resolves, by the
    /// form's path.
    form_sides: crate::hash::StableHashMap<NodePath, Side>,
    /// The columns of each node of the graph that hold an Example, by its
    /// index.
    examples: Box<[std::sync::Arc<[ExamplePath]>]>,
    /// The columns that hold an Example of each relation of a node whose
    /// forms give it several, by the node and the relation's path after
    /// the form's name, which a read of that relation reads.
    output_examples: crate::hash::StableHashMap<(GraphNodeIndex, std::sync::Arc<[OutputStep]>), std::sync::Arc<[ExamplePath]>>,
    resolutions: crate::hash::StableHashMap<NodePath, Resolution>,
    signatures: crate::hash::StableHashMap<NodePath, Signature>,
    positions: crate::hash::StableHashMap<NodePath, ColumnPosition>,
    label_positions: crate::hash::StableHashMap<(NodePath, LabelId), ColumnPosition>,
    groups: crate::hash::StableHashMap<NodePath, crate::relations::ColumnGroup>,
    proposer_columns: crate::hash::StableHashMap<(NodePath, usize), Box<[ColumnName]>>,
    /// The path of each read that its form reads in its lifted form.
    lifted: crate::hash::StableHashSet<NodePath>,
    names: names::Names,
    concept: Option<ConceptForms>,
}

/// The concept program of a case, and the path there of each `DET` form
/// that the case takes from it, by the form's path in the case.
#[derive(Clone, Debug)]
struct ConceptForms {
    program: Arc<ResolvedProgram>,
    paths: crate::hash::StableHashMap<NodePath, NodePath>,
}

impl ResolvedProgram {
    /// What the name read at `path` resolves to. Each path that a method of
    /// `ResolvedProgram` takes walks as [`crate::program::path::node_at`]
    /// gives.
    pub fn resolution(&self, path: &NodePath) -> Option<&Resolution> {
        self.resolutions.get(path)
    }

    /// The position, in the rows of the relation its atom reads, of the
    /// column that the site at `site` names. A site on a field of a record,
    /// such as `(:P P2)` in `(:key (:P P2))`, names that field's column of
    /// the record's column group, so it is told apart from a column of the
    /// same name, `(:P P2)` beside it.
    ///
    /// A [`crate::program::SiteArg::NamedLabel`] at `site` maps to the column
    /// of the field its name gives where its site reads a record, and to the
    /// site's own column where it does not, so each field of
    /// `(:key P_intile *Col)` has its own position. The value gives the
    /// field, so the mapping needs no layout.
    pub fn column_position(&self, site: &NodePath) -> Option<ColumnPosition> {
        self.positions.get(site).copied()
    }

    /// The position in the rows of its node of the column of `label`, a
    /// label of a column that the form at `form` gives: a clause's, or a
    /// `CHOOSE` form's row or candidate column. In a node of several forms,
    /// as a parameter that several blocks of a case determine, each form's
    /// column takes the position of the node's column of its name, as a
    /// site that reads the node names it.
    pub fn label_position(&self, form: &NodePath, label: LabelId) -> Option<ColumnPosition> {
        self.label_positions.get(&(form.clone(), label)).copied()
    }

    /// The column group that the site at `site` reads, where the site is on
    /// a column of a record, the key's or a type parameter's. A
    /// [`crate::program::SiteArg::NamedLabel`] at `site` maps to a column as
    /// [`ResolvedProgram::column_position`] gives.
    pub fn column_group(&self, site: &NodePath) -> Option<crate::relations::ColumnGroup> {
        self.groups.get(site).copied()
    }

    /// The side of `node` of the graph: by the keyword of its clause, and,
    /// for an `INIT`, a `CHOOSE` or a `DEMONSTRATED` form, by its key and
    /// what its bodies read.
    pub fn side(&self, node: GraphNodeIndex) -> Side {
        self.sides[node.0 as usize]
    }

    /// The side of the form at `form`, a form that gives no node of its own
    /// included, by what its reads read, or `None` where `form` is the path
    /// of no form whose reads the resolver resolves.
    pub fn form_side(&self, form: &NodePath) -> Option<Side> {
        self.form_sides.get(form).copied()
    }

    /// The columns that hold an Example of the relation of `node` of the
    /// graph that a read at `output` after the owner's name reads, each by
    /// its path, in no order: those of the relation a form of `node` gives
    /// at `output`, where one does, and otherwise those of each relation of
    /// `node`. [`output_of`] gives a read's `output`.
    pub fn example_columns(&self, node: GraphNodeIndex, output: Option<&[OutputStep]>) -> &[ExamplePath] {
        let at = output.and_then(|output| self.output_examples.get(&(node, std::sync::Arc::from(output))));
        at.unwrap_or(&self.examples[node.0 as usize])
    }

    /// The signature of the name read at `path`.
    pub fn signature(&self, path: &NodePath) -> Option<&Signature> {
        self.signatures.get(path)
    }

    /// The path of the form that gives `node` of the graph, so that the cycle
    /// check reports each form on a cycle: the first of
    /// [`ResolvedProgram::forms_of`], or the empty path for a fact.
    pub fn form_of(&self, node: GraphNodeIndex) -> &NodePath {
        static PROGRAM: std::sync::LazyLock<NodePath> = std::sync::LazyLock::new(NodePath::default);
        self.forms_of(node).first().unwrap_or(&PROGRAM)
    }

    /// The paths of the forms that give `node` of the graph, in the order
    /// the resolver declares them: none for a fact, several for a relation
    /// that several clauses derive.
    pub fn forms_of(&self, node: GraphNodeIndex) -> &[NodePath] {
        &self.forms[node.0 as usize]
    }

    /// The nodes of the graph that the form at `form` gives, in the order of
    /// their indices: none for a path that is no form's, several for an
    /// `INIT` form, which gives a node to each output and each input it
    /// writes. The inverse of [`ResolvedProgram::forms_of`].
    pub fn nodes_of(&self, form: &NodePath) -> &[GraphNodeIndex] {
        self.form_nodes.get(form).map_or(&[], |nodes| nodes)
    }

    /// Whether the form that holds the read at `read` reads its relation in
    /// its lifted form, as [`Side`] gives it.
    pub fn reads_lifted(&self, read: &NodePath) -> bool {
        self.lifted.contains(read)
    }

    /// The resolved content of the node at `path`, or `None` where `path`
    /// names no node. The empty path names the whole program, whose content
    /// is that of its forms, with no order and no names.
    pub fn content(&self, path: &NodePath) -> Option<ResolvedContent> {
        self.names.content(&self.program, path).map(|form| ResolvedContent { form })
    }

    /// The name of the stored parameter's column that each column of the
    /// proposer at `index` of the clause at `clause` stands for, in the
    /// proposer's column order. A `DET_OR_RULE` line maps a proposer's
    /// columns by that order onto the stored parameter's columns, and name
    /// resolution gives each the stored parameter's name.
    pub fn proposer_columns(&self, clause: &NodePath, index: usize) -> Option<&[ColumnName]> {
        self.proposer_columns.get(&(clause.clone(), index)).map(|columns| &columns[..])
    }

    /// The concept program that the case's concept `DET` forms resolve
    /// their reads in, as [`ConceptReads`] gives, or `None` for a program
    /// resolved with no [`ConceptReads`].
    pub fn concept(&self) -> Option<&ResolvedProgram> {
        self.concept.as_ref().map(|concept| &*concept.program)
    }

    /// The path in [`ResolvedProgram::concept`] of what stands at `path`,
    /// where `path` stands at or under a `DET` form that the case takes
    /// from the concept program.
    pub fn concept_path(&self, path: &NodePath) -> Option<NodePath> {
        let concept = self.concept.as_ref()?;
        (1..=path.0.len()).find_map(|len| {
            let form = NodePath(path.0[..len].into());
            rebase(path, &form, concept.paths.get(&form)?)
        })
    }
}

/// `path` with its prefix `from` replaced by `to`, where `from` is a
/// prefix of it.
fn rebase(path: &NodePath, from: &NodePath, to: &NodePath) -> Option<NodePath> {
    path.0.strip_prefix(&from.0[..]).map(|rest| to.join(&NodePath(rest.into())))
}

/// A column of a relation by its path: the column's name, then, on a
/// record, the field's.
pub type ExamplePath = Box<[ColumnName]>;

/// The path after the owner's name of the output that `relation` reads,
/// where it reads one.
pub fn output_of(relation: &RelationRef) -> Option<&[OutputStep]> {
    match relation {
        RelationRef::Output(output) => Some(&output.path),
        RelationRef::Declared(_) | RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => None,
    }
}

/// The concept program's resolution, which the `DET` forms that a case
/// takes from the concept program read through: each of those forms, at its
/// path in the case program, resolves its reads in `concept`, so it reads the
/// concept program's derivation in every case, and the case reads its
/// parameter as one node.
#[derive(Clone, Copy, Debug)]
pub struct ConceptReads<'a> {
    pub concept: &'a Arc<ResolvedProgram>,
    /// The paths in the case program of the concept program's `DET` forms,
    /// as [`crate::solver::Case::concept_determinations`] gives them.
    pub determinations: &'a [NodePath],
}

/// What every case of a solver resolves against, as
/// [`crate::solver::Solver::derived_relations`] gives it, or a synthesized
/// program's own.
#[derive(Clone, Debug, Default)]
pub struct SolverScope {
    /// The relations that some block of the solver derives, as
    /// [`crate::solver::Solver::derived`] gives them.
    pub derived: crate::hash::StableHashSet<ProgramRelation>,
    /// The column names that the sites of the reads of each relation name
    /// across the solver's cases, as [`crate::solver::Solver::read_columns`]
    /// gives them.
    pub read_columns: crate::hash::StableHashMap<ProgramRelation, Vec<ColumnName>>,
}

/// Adds to `names` each of `columns` that it does not hold, in order.
pub(crate) fn add_columns<'c>(names: &mut Vec<ColumnName>, columns: impl IntoIterator<Item = &'c ColumnName>) {
    for column in columns {
        if !names.contains(column) {
            names.push(column.clone());
        }
    }
}

/// Resolves the names of `case`, a case program that `crate::solver` gives,
/// or a synthesized program. `concept` is `None` for a synthesized program
/// and for the concept case. `scope` holds what the cases of the solver
/// share, or a synthesized program's own: a name among its derived relations
/// that no block of the case derives is [`Resolution::Undefined`], and a name among none is
/// [`Resolution::Unresolved`].
///
/// Gives a diagnostic of the scope at each name that resolves to nothing and
/// is no relation a block could derive, which resolves to
/// [`Resolution::Unresolved`], so that every other check still runs over
/// the case.
pub fn resolve(
    case: &Node<Program>,
    concept: Option<ConceptReads<'_>>,
    scope: &SolverScope,
    registry: &Registry,
) -> WithDiagnostics<ResolvedProgram> {
    build::resolve(case, concept, scope, registry)
}

/// A case of a solver with its resolution and the diagnostics of that
/// resolution.
#[derive(Debug)]
pub struct ResolvedCase {
    pub case: crate::solver::Case,
    pub resolved: WithDiagnostics<Arc<ResolvedProgram>>,
}

/// The resolution of each case of a solver, as [`resolve_cases`] gives it:
/// the concept case's, with no [`ConceptReads`], and each other case's, with
/// the [`ConceptReads`] of the concept case's resolution and the case's
/// [`crate::solver::Case::concept_determinations`].
#[derive(Debug)]
pub struct ResolvedCases {
    concept: ResolvedCase,
    /// Whether [`crate::solver::Solver::cases`] gives the concept case,
    /// which it does not where a `representative` line names another case.
    concept_is_a_case: bool,
    /// The cases of [`crate::solver::Solver::cases`] other than the concept
    /// case, in its order.
    others: Box<[ResolvedCase]>,
}

impl ResolvedCases {
    /// The concept case and its resolution.
    pub fn concept(&self) -> &ResolvedCase {
        &self.concept
    }

    /// Each case that [`crate::solver::Solver::cases`] gives with
    /// [`crate::solver::Exclusion::WithExcluded`], with its resolution, in
    /// its order, the concept case first.
    pub fn cases(&self) -> impl Iterator<Item = &ResolvedCase> {
        self.concept_is_a_case.then_some(&self.concept).into_iter().chain(self.others.iter())
    }

    /// Each case resolved: the concept case, then each other case of
    /// [`ResolvedCases::cases`].
    pub fn resolved(&self) -> impl Iterator<Item = &ResolvedCase> {
        std::iter::once(&self.concept).chain(self.others.iter())
    }
}

/// Resolves the concept case of `solver`, and then each other case of
/// [`crate::solver::Solver::cases`] with
/// [`crate::solver::Exclusion::WithExcluded`], with the [`ConceptReads`] of
/// the concept case's resolution, against
/// [`crate::solver::Solver::derived_relations`].
pub fn resolve_cases(solver: &crate::solver::Solver, registry: &Registry) -> ResolvedCases {
    let scope = solver.derived_relations();
    let concept_case = solver.concept_case();
    let shared = |resolved: WithDiagnostics<ResolvedProgram>| WithDiagnostics { value: Arc::new(resolved.value), diagnostics: resolved.diagnostics };
    let concept = shared(resolve(&concept_case.program, None, &scope, registry));
    let mut concept_is_a_case = false;
    let mut others = Vec::new();
    for case in solver.cases(crate::solver::Exclusion::WithExcluded) {
        if case.name == concept_case.name {
            concept_is_a_case = true;
            continue;
        }
        let reads = ConceptReads { concept: &concept.value, determinations: case.concept_determinations() };
        let resolved = shared(resolve(&case.program, Some(reads), &scope, registry));
        others.push(ResolvedCase { case, resolved });
    }
    ResolvedCases { concept: ResolvedCase { case: concept_case, resolved: concept }, concept_is_a_case, others: others.into() }
}

/// Each `DEMO_RULE` form of the `DEMONSTRATED` form at `path`, with its
/// path: its children after the key clause and the inputs.
fn demo_rules<'d>(
    demonstrated: &'d crate::program::Demonstrated,
    path: &NodePath,
) -> impl Iterator<Item = (NodePath, &'d crate::program::DemoRule)> + 'd {
    let path = path.clone();
    let rules = demonstrated.rules.iter().enumerate();
    rules.map(move |(index, rule)| (path.child(demonstrated.position(crate::program::DemonstratedPart::Rule(index))), rule.value()))
}

pub(crate) mod columns;
pub(crate) mod form_columns;
pub(crate) mod registry_columns;

mod names;

mod build;
