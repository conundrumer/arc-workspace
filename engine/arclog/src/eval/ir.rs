//! The clause IR, the evaluator's form of a body after name resolution: a
//! conjunctive query with filters and unions, over
//! resolved relations, and the compilation of a body's positive
//! conjunctive part into it.
//!
//! A variable of the IR is a label of the body at its canonical position,
//! so two bodies of equal resolved content compile to equal IR, and an
//! order over variables that breaks ties by their index breaks them by
//! content. [`crate::eval::filters`] compiles `NOT`, `ALL`, `IF` and `OR`
//! through [`IrBuilder`].

use std::hash::{Hash, Hasher};
use std::rc::Rc;
use std::sync::OnceLock;

use crate::check::CheckedProgram;
use crate::hash::StableHashSet;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{
    Atom, Body, Conjunct, ConstraintOp, FactRelation, LabelId, LabelUse, ProgramRelation, RelationRef, Site, SiteArg,
};
use crate::registry::{LibName, Mode, Registry};
use crate::relations::ColumnIndex;
use crate::resolver::{DependencyKind, Resolution};
use crate::terms::TermId;
use crate::types::{FormTypes, GraphRelation, ValueType};

/// A variable of a clause: the canonical position of its label in the
/// body, an index into [`ClauseIr::variables`].
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Variable(pub u16);

/// A variable's type, which the type check inferred for its label.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct VariableInfo {
    pub ty: ValueType,
}

/// What stands at one column of an atom: a variable, or a term, such as
/// `0`'s.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Argument {
    Variable(Variable),
    Term(TermId),
}

/// The columns an atom reads, each with what stands at it. A column the
/// atom leaves out is projected away.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Arguments(pub Box<[(ColumnIndex, Argument)]>);

/// The relation an atom reads.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum AtomSource {
    /// `input`, `ex_input` or `ex_output`.
    Fact(FactRelation),
    /// A relation of the dependency graph: a clause's, a parameter, a
    /// chosen relation, an output of an instance or of a `RIGID_DET`.
    Relation(GraphRelation),
    /// A relation that no block of the case derives: the clause's relation
    /// is `undefined` wherever the clause reads it.
    Undefined(ProgramRelation),
    /// The rows of an `INIT` or `DEMONSTRATED` form's key clause, whose
    /// columns are the key's labels in order.
    Key(Box<KeyRead>),
}

/// The key clause of the form at `form`, which a keyed input of the form
/// reads in place of the key body: a label of the key body with no `^` is
/// local to it, and the input reads the key's columns alone.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct KeyRead {
    pub form: NodePath,
    pub clause: ClauseIr,
}

/// An atom of a relation with rows: a fact relation or a relation of the
/// dependency graph.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct RelationAtom {
    pub source: AtomSource,
    /// Whether the atom is a lifted read of the train examples alone
    /// ([`crate::resolver::ResolvedProgram::reads_train_examples`]).
    pub train_only: bool,
    pub arguments: Arguments,
}

/// An atom of an algebra relation of the lib, evaluated as a native
/// function at a mode, as [`crate::algebra`] gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct LibAtom {
    pub relation: LibName,
    pub arguments: Arguments,
}

/// The second operand of a comparison.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Operand {
    Variable(Variable),
    /// `0`, at the type of the first operand.
    Zero,
}

/// `=` or a comparison over two operands. An `=` that makes its variable
/// binds it, and every other comparison is a filter on bound variables.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Comparison {
    pub op: ConstraintOp,
    pub first: Variable,
    pub second: Operand,
    /// Whether the comparison makes its first variable, as `(= *X Y)` does.
    pub binds_first: bool,
}

/// A filter's body: a clause over the filter's outer variables and its own
/// local ones, probed once the outer variables are bound, as
/// [`crate::eval::filters`] gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Filter {
    /// The variables of the enclosing clause that the filter reads.
    pub outer: Box<[Variable]>,
    pub body: Box<ClauseIr>,
}

/// An `OR`, or an `IF` as the two clauses of
/// `docs/arclog/arclog.md#conditional`: its branches, each a clause, and the
/// variables it exports to the enclosing clause, which every branch binds.
/// A branch's columns are the variables it shares with the enclosing
/// clause, those it exports included.
///
/// The branches stand in the order they are written, which the relation of
/// the union lists its rows in. The evaluator searches them in
/// [`Union::canonical`], so that the work of a union follows its content. The
/// equality and the hash of a union hold its exports and branches, and not
/// that order.
#[derive(Clone, Debug)]
pub struct Union {
    pub exported: Box<[Variable]>,
    pub branches: Box<[ClauseIr]>,
    /// The index of the branch at each place of the canonical order of the
    /// branches: the order of their canonical paths in the program's
    /// canonical form.
    pub canonical: Box<[u32]>,
}

impl PartialEq for Union {
    fn eq(&self, other: &Self) -> bool {
        self.exported == other.exported && self.branches == other.branches
    }
}

impl Eq for Union {}

impl Hash for Union {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.exported.hash(state);
        self.branches.hash(state);
    }
}

impl Union {
    /// The index of each branch, in the canonical order of the branches.
    pub fn in_canonical_order(&self) -> impl Iterator<Item = usize> + '_ {
        self.canonical.iter().map(|&index| index as usize)
    }

    /// Whether the canonical order of the branches is the order written.
    pub fn is_written_order(&self) -> bool {
        self.canonical.iter().zip(0u32..).all(|(&index, at)| index == at)
    }
}

/// One node of a clause.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum IrNode {
    Atom(RelationAtom),
    Lib(LibAtom),
    Comparison(Comparison),
    /// A `NOT`: the binding passes where the filter holds no binding.
    Not(Filter),
    /// The counterexample relation of an `ALL`
    /// (`docs/arclog/arclog.md#universal`): the binding passes where the
    /// filter, a member of the domain that fails the body, holds no binding.
    Counterexample(Filter),
    Or(Union),
}

/// A clause: its variables, its nodes, and the variables its relation
/// holds as columns, in the order of the relation's columns.
///
/// The nodes of a clause stand in the order of the conjuncts as written, which
/// the readers of the IR follow, or, in a clause that a compile in canonical
/// order gives, in the canonical order of the conjuncts. The evaluator joins
/// a clause in its canonical order, [`ClauseIr::in_canonical_order`], so that
/// its work is a function of the clause's content. The equality and the hash
/// of a clause hold its variables, nodes and columns, and neither of the two
/// orders.
#[derive(Clone, Debug)]
pub struct ClauseIr {
    pub variables: Box<[VariableInfo]>,
    pub nodes: Box<[IrNode]>,
    pub columns: Box<[Variable]>,
    /// The place of each node in the canonical order of the conjuncts that
    /// the nodes compile, by the node's index: the order of the conjuncts'
    /// canonical paths in the program's canonical form.
    pub canonical: Box<[u32]>,
    /// The index of each node in the clause as written, by the node's index.
    /// A clause in canonical order holds there the places its nodes had.
    pub written: Box<[u32]>,
    /// This clause in canonical order, made on the first use of
    /// [`ClauseIr::in_canonical_order`]; none where the nodes stand in it.
    /// The fields above are fixed from the first use on.
    joined: Joined,
}

/// The clause that [`ClauseIr::in_canonical_order`] gives, which the clause
/// holds. A clone of a clause holds none.
#[derive(Debug, Default)]
struct Joined(OnceLock<Option<Box<ClauseIr>>>);

impl Clone for Joined {
    fn clone(&self) -> Self {
        Joined::default()
    }
}

impl PartialEq for ClauseIr {
    fn eq(&self, other: &Self) -> bool {
        self.variables == other.variables && self.nodes == other.nodes && self.columns == other.columns
    }
}

impl Eq for ClauseIr {}

impl Hash for ClauseIr {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.variables.hash(state);
        self.nodes.hash(state);
        self.columns.hash(state);
    }
}

/// Whether the driver prints, to the standard error, one line for each clause
/// whose evaluation did work: `arclog-join-measure form=<path> nodes=<n>
/// work=<n> ns=<n>`. The work and the time include those of the clauses it
/// reads. `ARCLOG_JOIN_MEASURE` set to a value other than `0` or empty, read
/// once. It changes no result.
pub fn measures() -> bool {
    static MEASURES: OnceLock<bool> = OnceLock::new();
    *MEASURES.get_or_init(|| std::env::var("ARCLOG_JOIN_MEASURE").is_ok_and(|value| !value.is_empty() && value != "0"))
}

impl ClauseIr {
    /// A clause whose nodes stand in the order they are given, which is also
    /// the order they are joined in.
    pub fn new(variables: Box<[VariableInfo]>, nodes: Box<[IrNode]>, columns: Box<[Variable]>) -> Self {
        let identity: Box<[u32]> = (0..nodes.len() as u32).collect();
        ClauseIr { variables, nodes, columns, canonical: identity.clone(), written: identity, joined: Joined::default() }
    }

    /// Whether the nodes stand in canonical order, here and in each clause
    /// nested in them.
    fn is_canonical(&self) -> bool {
        self.canonical.iter().zip(0u32..).all(|(&place, at)| place == at) && self.nodes.iter().all(IrNode::is_canonical)
    }

    /// The index of the node at each place of the canonical order.
    fn canonical_nodes(&self) -> Vec<usize> {
        let mut at: Vec<usize> = (0..self.nodes.len()).collect();
        at.sort_by_key(|&node| self.canonical[node]);
        at
    }

    /// This clause with its nodes in canonical order, and the clauses nested
    /// in them likewise: the clause the evaluator joins. Two clauses of one
    /// content, whose conjuncts are written in two orders, give one clause.
    /// The relation's columns, and so its rows and their columns, are those of
    /// this clause. The clause is made on the first call and kept; a clause
    /// whose nodes stand in canonical order gives itself.
    pub fn in_canonical_order(&self) -> &ClauseIr {
        self.joined.0.get_or_init(|| (!self.is_canonical()).then(|| Box::new(self.reordered()))).as_deref().unwrap_or(self)
    }

    fn reordered(&self) -> ClauseIr {
        let at = self.canonical_nodes();
        ClauseIr {
            variables: self.variables.clone(),
            nodes: at.iter().map(|&node| self.nodes[node].in_canonical_order()).collect(),
            columns: self.columns.clone(),
            canonical: (0..at.len() as u32).collect(),
            written: at.iter().map(|&node| self.written[node]).collect(),
            joined: Joined::default(),
        }
    }

    /// This clause with the union at node `at` replaced by the nodes of its
    /// `branch`, which stand where the union stood, in the canonical order
    /// among themselves.
    pub fn splice(&self, at: usize, branch: &ClauseIr) -> ClauseIr {
        let mut parts: Vec<((u32, u32), IrNode)> = Vec::with_capacity(self.nodes.len() + branch.nodes.len());
        for (index, node) in self.nodes.iter().enumerate() {
            if index == at {
                parts.extend(branch.nodes.iter().zip(branch.canonical.iter()).map(|(inner, &place)| ((self.canonical[at], place), inner.clone())));
            } else {
                parts.push(((self.canonical[index], 0), node.clone()));
            }
        }
        let mut places: Vec<usize> = (0..parts.len()).collect();
        places.sort_by_key(|&part| parts[part].0);
        let mut canonical = vec![0u32; parts.len()];
        for (place, &part) in places.iter().enumerate() {
            canonical[part] = place as u32;
        }
        let written: Box<[u32]> = (0..parts.len() as u32).collect();
        let nodes: Box<[IrNode]> = parts.into_iter().map(|(_, node)| node).collect();
        ClauseIr { variables: self.variables.clone(), nodes, columns: self.columns.clone(), canonical: canonical.into(), written, joined: Joined::default() }
    }
}

impl IrNode {
    /// Whether the clauses nested in the node stand in canonical order.
    fn is_canonical(&self) -> bool {
        match self {
            IrNode::Not(filter) | IrNode::Counterexample(filter) => filter.body.is_canonical(),
            IrNode::Or(union) => union.branches.iter().all(ClauseIr::is_canonical),
            IrNode::Atom(RelationAtom { source: AtomSource::Key(key), .. }) => key.clause.is_canonical(),
            _ => true,
        }
    }

    /// This node with the clauses nested in it in canonical order. The
    /// branches of a union stand in the order they are written: the rows of
    /// the union are listed in that order.
    fn in_canonical_order(&self) -> IrNode {
        let filter = |filter: &Filter| Filter { outer: filter.outer.clone(), body: Box::new(filter.body.reordered()) };
        match self {
            IrNode::Not(inner) => IrNode::Not(filter(inner)),
            IrNode::Counterexample(inner) => IrNode::Counterexample(filter(inner)),
            IrNode::Or(union) => IrNode::Or(Union {
                exported: union.exported.clone(),
                branches: union.branches.iter().map(ClauseIr::reordered).collect(),
                canonical: union.canonical.clone(),
            }),
            IrNode::Atom(RelationAtom { source: AtomSource::Key(key), train_only, arguments }) => IrNode::Atom(RelationAtom {
                source: AtomSource::Key(Box::new(KeyRead { form: key.form.clone(), clause: key.clause.reordered() })),
                train_only: *train_only,
                arguments: arguments.clone(),
            }),
            other => other.clone(),
        }
    }
}

/// What a node of a clause stands on in the program text.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum NodePaths {
    /// The path of the atom that an `Atom` or a `Lib` node compiles.
    Atom(NodePath),
    /// The paths of the key clause of an `Atom` node whose source is
    /// [`AtomSource::Key`].
    Key(Box<IrPaths>),
    /// The paths of each branch of an `Or` node.
    Branches(Box<[IrPaths]>),
    /// The paths of the body of a `Not` or a `Counterexample` node.
    Filter(Box<IrPaths>),
    /// A comparison: no atom of the program text to read from.
    None,
}

/// Where the nodes of a [`ClauseIr`] stand in the program text, beside the
/// clause: the IR holds no path, since the result cache keys a body by the
/// IR's content, which equal bodies at different paths share.
#[derive(Clone, PartialEq, Eq, Debug, Default)]
pub struct IrPaths {
    /// The label of each variable of the clause, by the variable's index.
    pub labels: Box<[LabelId]>,
    /// The paths of each node of the clause, by the node's index.
    pub nodes: Box<[NodePaths]>,
}

/// A body that the IR cannot hold: a safe subset of a body is
/// required, and a subset that leaves a label unbound is refused with
/// those labels; a form whose scope holds a label that the checked program
/// gives no type is refused with that label.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum CompileFault {
    Unbound { labels: Box<[LabelId]> },
    Untyped { label: LabelId },
}

/// What one compile takes: the path of each conjunct it compiles, and the
/// labels of the columns of the relation it gives.
#[derive(Debug)]
pub struct Compiled {
    pub conjuncts: Box<[NodePath]>,
    pub columns: Box<[LabelId]>,
}

/// The state of a compilation of one body: the variables given so far and
/// the nodes compiled so far.
#[derive(Debug)]
pub struct IrBuilder<'a> {
    pub program: &'a CheckedProgram,
    /// The path of the form whose body is compiled, whose label types the
    /// variables take.
    pub form: NodePath,
    /// What the compile that this builder or the builder it is nested in
    /// serves takes.
    pub compiled: Rc<Compiled>,
    /// The canonical order of the top-level form that holds `form`.
    order: &'a CanonicalOrder,
    /// Whether [`IrBuilder::finish`] puts the nodes in canonical order, with
    /// their paths, and not in the order the conjuncts are written.
    pub(super) canonical_order: bool,
    variables: Vec<VariableInfo>,
    nodes: Vec<IrNode>,
    /// The label of each variable.
    labels: Vec<LabelId>,
    /// The paths of each node of `nodes`.
    paths: Vec<NodePaths>,
    /// The canonical path of the conjunct that each node of `nodes`
    /// compiles, which gives the node its place in the canonical order.
    keys: Vec<Vec<u32>>,
    /// The canonical path of the conjunct being compiled, or [`AFTER`].
    current: Vec<u32>,
}

/// The key of a node that stands after the nodes of every conjunct: a node
/// that a filter or a branch adds beside its conjuncts.
const AFTER: [u32; 1] = [u32::MAX];

impl<'a> IrBuilder<'a> {
    /// A builder over the body of the form at `form` of `program`, for a
    /// compile that takes `compiled`, or the fault of a label of the form's
    /// scope that `program` gives no type.
    pub fn new(program: &'a CheckedProgram, form: NodePath, compiled: Rc<Compiled>) -> Result<Self, CompileFault> {
        let (first, scope) = form.0.split_first().expect("the path of a form of the program");
        let top = &program.program.program.value().forms[first.0 as usize];
        let order = CanonicalOrder::of(top, &mut SearchBudget::new());
        let scope = NodePath(scope.into());
        let types = form_types(program, &form);
        let labels = order.labels_of(&scope).unwrap_or_default();
        let mut variables = vec![None; labels.len()];
        let mut held = vec![None; variables.len()];
        for &(label, position) in labels {
            let ty = types.label(label).ok_or(CompileFault::Untyped { label })?.clone();
            variables[position as usize] = Some(VariableInfo { ty });
            held[position as usize] = Some(label);
        }
        let variables = variables.into_iter().map(|info| info.expect("a label at each canonical position")).collect();
        let labels = held.into_iter().map(|label| label.expect("a label at each canonical position")).collect();
        Ok(IrBuilder { program, form, compiled, order, canonical_order: false, variables, nodes: Vec::new(), labels, paths: Vec::new(), keys: Vec::new(), current: AFTER.to_vec() })
    }

    /// The variable of `label`: its canonical position in the form's scope.
    pub fn variable(&self, label: LabelId) -> Variable {
        let scope = NodePath(self.form.0[1..].into());
        Variable(u16::try_from(self.order.canonical_label(&scope, label)).expect("fewer than 2^16 labels in a scope"))
    }

    /// Adds `node` to the clause, which stands on `paths` in the program
    /// text.
    pub fn push(&mut self, node: IrNode, paths: NodePaths) {
        self.nodes.push(node);
        self.paths.push(paths);
        self.keys.push(self.current.clone());
    }

    /// Adds `node` to the clause ahead of the nodes of every conjunct in the
    /// canonical order.
    fn push_first(&mut self, node: IrNode, paths: NodePaths) {
        self.nodes.push(node);
        self.paths.push(paths);
        self.keys.push(Vec::new());
    }

    /// The canonical path of the node at `path`, a path in the program,
    /// below the form, as the steps of its path.
    pub(super) fn key_of(&self, path: &NodePath) -> Vec<u32> {
        let relative = NodePath(path.0.get(1..).unwrap_or_default().into());
        let placed = self.order.try_canonical_path(&relative).unwrap_or(relative);
        placed.0.iter().map(|step| step.0).collect()
    }

    /// Compiles the conjuncts of `body` at `path` into the clause: its atoms
    /// and its comparisons here, and each `NOT`, `ALL`, `IF` and `OR`
    /// through [`crate::eval::filters`].
    pub fn body(&mut self, body: &Body, path: &NodePath) -> Result<(), CompileFault> {
        for (conjunct, index) in body.conjuncts.iter().zip(0u32..) {
            self.conjunct(conjunct, &path.child(index))?;
        }
        Ok(())
    }

    /// Compiles one conjunct at `path`. Its nodes stand at the conjunct's
    /// place in the canonical order of the body's conjuncts.
    pub(super) fn conjunct(&mut self, conjunct: &Conjunct, path: &NodePath) -> Result<(), CompileFault> {
        let key = self.key_of(path);
        let outer = std::mem::replace(&mut self.current, key);
        let compiled = self.compile_conjunct(conjunct, path);
        self.current = outer;
        compiled
    }

    fn compile_conjunct(&mut self, conjunct: &Conjunct, path: &NodePath) -> Result<(), CompileFault> {
        match conjunct {
            Conjunct::Atom(atom) => {
                let node = self.atom(atom.value(), path);
                self.push(node, NodePaths::Atom(path.clone()));
            }
            Conjunct::Constraint(constraint) => {
                let first = self.variable(constraint.first.label);
                let second = match constraint.second {
                    crate::program::Operand::Label(label) => Operand::Variable(self.variable(label.label)),
                    crate::program::Operand::Zero => Operand::Zero,
                };
                self.push(IrNode::Comparison(Comparison { op: constraint.op, first, second, binds_first: constraint.first.fresh }), NodePaths::None);
            }
            Conjunct::Not(negated) => super::filters::compile_not(self, negated, path)?,
            Conjunct::All { domain, body } => super::filters::compile_all(self, domain, body, path)?,
            Conjunct::If { test, then, otherwise } => super::filters::compile_if(self, test, then, otherwise, path)?,
            Conjunct::Or(branches) => super::filters::compile_or(self, branches, path)?,
        }
        Ok(())
    }

    /// The node of the positive atom at `path`, by what its relation
    /// resolves to.
    fn atom(&mut self, atom: &Atom, path: &NodePath) -> IrNode {
        let mut arguments = Vec::new();
        for (site, index) in atom.sites.iter().zip(0u32..) {
            self.site(site, &path.child(index), &mut arguments);
        }
        let arguments = Arguments(arguments.into());
        if let RelationRef::Fact(fact) = &atom.relation {
            return IrNode::Atom(RelationAtom { source: AtomSource::Fact(*fact), train_only: false, arguments });
        }
        let resolved = self.program.program.resolution(path).expect("a resolution of each atom of a checked form");
        let source = match resolved {
            Resolution::Node(node) => {
                let kind = &self.program.program.graph.nodes[node.0 as usize].kind;
                let output = match (&atom.relation, kind) {
                    (RelationRef::Output(name), DependencyKind::RigidAssembly(_) | DependencyKind::RecursiveInstance(_)) => {
                        Some(name.path.clone())
                    }
                    _ => None,
                };
                AtomSource::Relation(GraphRelation { node: *node, output })
            }
            Resolution::Lib(name) => return IrNode::Lib(LibAtom { relation: name.clone(), arguments }),
            Resolution::Undefined(relation) => AtomSource::Undefined(relation.clone()),
            Resolution::Unresolved => unreachable!("a checked form resolves each name it reads"),
        };
        IrNode::Atom(RelationAtom { source, train_only: self.program.program.reads_train_examples(path), arguments })
    }

    /// Adds to `arguments` the column and the argument of each label of the
    /// site at `path`: the site's own column, or, at a record's column
    /// group, the column of each field.
    fn site(&mut self, site: &Site, path: &NodePath, arguments: &mut Vec<(ColumnIndex, Argument)>) {
        let resolved = &self.program.program;
        let position = |path: &NodePath| {
            let found = resolved.column_position(path).expect("a column position of each site of a checked form");
            ColumnIndex(found.0)
        };
        if let Some(own) = resolved.column_position(path) {
            for arg in site.value.args.iter() {
                let label = arg.label().expect("a label at a site on one column");
                arguments.push((ColumnIndex(own.0), self.argument(label)));
            }
            return;
        }
        for (arg, index) in site.value.args.iter().zip(0u32..) {
            let label = match arg {
                SiteArg::NamedLabel { label, .. } => *label,
                SiteArg::Field(field) => {
                    let [SiteArg::Label(label)] = &field.value.args[..] else {
                        panic!("a field site of one label")
                    };
                    *label
                }
                SiteArg::Label(_) => panic!("a site on a record names each of its fields"),
            };
            arguments.push((position(&path.child(index)), self.argument(label)));
        }
    }

    /// What `label` stands for at a site: its variable, or `0`'s term.
    fn argument(&mut self, label: LabelUse) -> Argument {
        match label {
            LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label) => Argument::Variable(self.variable(label)),
            LabelUse::Zero => Argument::Term(TermId::from_encoding(0)),
        }
    }

    /// The clause, whose relation holds `columns`, with the paths of its
    /// nodes: in the order of the conjuncts as written, or, where
    /// [`IrBuilder::canonical_order`] holds, in their canonical order, each
    /// node and its paths moved to its place.
    pub fn finish(self, columns: Box<[Variable]>) -> (ClauseIr, IrPaths) {
        let mut at: Vec<usize> = (0..self.nodes.len()).collect();
        at.sort_by(|&a, &b| self.keys[a].cmp(&self.keys[b]));
        let count = at.len() as u32;
        let (nodes, paths, canonical, written): (Vec<IrNode>, Vec<NodePaths>, Vec<u32>, Vec<u32>) = if self.canonical_order {
            let written = at.iter().map(|&node| node as u32).collect();
            (moved(self.nodes, &at), moved(self.paths, &at), (0..count).collect(), written)
        } else {
            let mut canonical = vec![0u32; at.len()];
            for (place, &node) in at.iter().enumerate() {
                canonical[node] = place as u32;
            }
            (self.nodes, self.paths, canonical, (0..count).collect())
        };
        let paths = IrPaths { labels: self.labels.into(), nodes: paths.into() };
        (ClauseIr { variables: self.variables.into(), nodes: nodes.into(), columns, canonical: canonical.into(), written: written.into(), joined: Joined::default() }, paths)
    }
}

/// `items` moved to the order of `at`, the index in `items` of each item of
/// the result.
fn moved<T>(items: Vec<T>, at: &[usize]) -> Vec<T> {
    let mut slots: Vec<Option<T>> = items.into_iter().map(Some).collect();
    at.iter().map(|&index| slots[index].take().expect("each item once")).collect()
}

/// The types of the labels of the scope at `form`.
fn form_types<'p>(program: &'p CheckedProgram, form: &NodePath) -> &'p FormTypes {
    program.types.form(form).expect("the label types of each scope of a checked program")
}

/// The modes of the relation `atom` reads: an algebra relation's or a
/// relation macro's, and none for every other relation.
pub fn atom_modes<'r>(registry: &'r Registry, atom: &Atom) -> &'r [Mode] {
    relation_modes(registry, &atom.relation)
}

/// The modes of `relation`: an algebra relation's or a relation macro's,
/// and none for every other relation.
pub fn relation_modes<'r>(registry: &'r Registry, relation: &RelationRef) -> &'r [Mode] {
    let RelationRef::Lib(name) = relation else { return &[] };
    registry.algebra_relation(name).map_or(&[], |relation| &relation.modes)
}

/// The path of the form whose label scope holds the labels of the form at
/// `path`: the innermost label scope of the canonical labeling,
/// [`CanonicalOrder::label_scopes`], whose form holds it.
/// The native innermost label scope of a nonempty checked program-form path.
/// Metadata consumers share the same lookup as IR compilation.
pub(crate) fn scope_of(program: &CheckedProgram, path: &NodePath) -> NodePath {
    let (first, within) = path.0.split_first().expect("the path of a form of the program");
    let top = &program.program.program.value().forms[first.0 as usize];
    let order = CanonicalOrder::of(top, &mut SearchBudget::new());
    let inner = order.label_scopes().into_iter().map(|(scope, _)| scope).filter(|scope| within.starts_with(&scope.0)).max_by_key(|scope| scope.0.len());
    NodePath(std::iter::once(*first).chain(inner.into_iter().flat_map(|scope| scope.0.into_vec())).collect())
}

/// The body and the columns of the form at `clause`, with the path of the
/// body: a clause's body and the labels of its node's columns, in the order
/// of the node's columns, a label of no column of the node projected away,
/// or an instance input's body and the labels of its head sites, in their
/// order.
fn form_body<'p>(program: &'p CheckedProgram, clause: &NodePath) -> (&'p Body, NodePath, Vec<LabelId>) {
    let root = NodeRef::Program(program.program.program.value());
    match node_at(root, clause).expect("the path of a form of the program") {
        NodeRef::Clause(form) => {
            let columns = relation_columns(&program.program, clause, NodeRef::Clause(form));
            (form.body.value(), clause.child(0), columns)
        }
        NodeRef::InstanceInput(input) => {
            let mut labels = Vec::new();
            for site in input.head.iter() {
                crate::types::each_site_label(site, &mut Vec::new(), &mut |use_, _| labels.extend(crate::types::use_label(use_)));
            }
            (input.body.value(), clause.child(input.position(crate::program::InstanceInputPart::Body)), labels)
        }
        _ => panic!("a clause or an instance input"),
    }
}

/// The labels of the columns of the relation of the form `shape` at `form`,
/// a clause or a `CHOOSE` form, in the order of the relation's columns:
/// the order of their positions, a label of no column of the node left out.
pub(crate) fn relation_columns(program: &crate::resolver::ResolvedProgram, form: &NodePath, shape: NodeRef<'_>) -> Vec<LabelId> {
    let mut columns: Vec<(u16, LabelId)> = crate::resolver::form_columns::form_columns(shape)
        .filter_map(|column| Some((program.label_position(form, column.label)?.0, column.label)))
        .collect();
    columns.sort_by_key(|(position, _)| *position);
    columns.into_iter().map(|(_, label)| label).collect()
}

/// The IR of the conjuncts at `kept`, indexes into the body of the form at
/// `clause`, as [`compile_clause`] gives a whole body. The relation's
/// columns are the form's columns whose labels the kept conjuncts hold.
/// Where the kept conjuncts leave a label unbound, as
/// [`crate::safety::bound_labels`] gives the bound labels, this refuses them
/// with those labels.
pub fn compile_conjuncts(program: &CheckedProgram, clause: &NodePath, kept: &[u32]) -> Result<ClauseIr, CompileFault> {
    compile_body(program, clause, kept).map(|body| body.clause)
}

/// The IR of a body's conjuncts, with the conjunct each of its nodes
/// compiles and the label of each of its columns, from which the parts of
/// the body are made.
#[derive(Debug)]
pub struct CompiledBody {
    pub clause: ClauseIr,
    /// The paths of the nodes of `clause`.
    pub paths: IrPaths,
    /// The index in the form's body of the conjunct that each node of
    /// `clause` compiles, by the node's index.
    pub conjuncts: Box<[u32]>,
    /// The label of each column of `clause`, in the order of its columns.
    pub columns: Box<[LabelId]>,
}

/// The order of the nodes that a compile gives.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum NodeOrder {
    /// The order of the conjuncts as written, which the readers of the IR
    /// follow.
    Written,
    /// The canonical order of the conjuncts, in which the evaluator joins.
    /// Each node stands with its paths and its conjunct at its place, in the
    /// clause and in each clause nested in it, and [`ClauseIr::written`]
    /// holds the index it had in the order written.
    Canonical,
}

/// The IR of the conjuncts at `kept`, as [`compile_conjuncts`] gives it,
/// with the conjunct of each node and the label of each column.
pub fn compile_body(program: &CheckedProgram, clause: &NodePath, kept: &[u32]) -> Result<CompiledBody, CompileFault> {
    compile_body_in(program, clause, kept, NodeOrder::Written)
}

/// [`compile_body`], with the nodes in `order`.
pub fn compile_body_in(program: &CheckedProgram, clause: &NodePath, kept: &[u32], order: NodeOrder) -> Result<CompiledBody, CompileFault> {
    let (body, body_path, columns) = form_body(program, clause);
    let conjuncts = kept.iter().map(|&index| (&body.conjuncts[index as usize], body_path.child(index))).collect();
    let mapped = compile_mapped(program, clause, None, conjuncts, &columns, order)?;
    Ok(CompiledBody { clause: mapped.clause, paths: mapped.paths, conjuncts: mapped.of_node.into_iter().map(|at| kept[at]).collect(), columns: mapped.columns })
}

/// The IR of the bodies `bodies` of the `INIT` form at `instance`, each with
/// its path, as one clause whose relation's columns are the labels
/// `columns`, in their order: a key body alone, whose columns are the
/// key's labels, or an input's body. A label of `columns`
/// that no body holds is no column of the relation. Where the bodies leave
/// a label unbound, this refuses them with those labels, as
/// [`compile_conjuncts`] does.
pub fn compile_instance_body(
    program: &CheckedProgram,
    instance: &NodePath,
    bodies: &[(&Body, NodePath)],
    columns: &[LabelId],
) -> Result<ClauseIr, CompileFault> {
    compile_instance_pathed(program, instance, bodies, columns).map(|(clause, _)| clause)
}

/// [`compile_instance_body`], with the paths of the clause's nodes.
pub fn compile_instance_pathed(
    program: &CheckedProgram,
    instance: &NodePath,
    bodies: &[(&Body, NodePath)],
    columns: &[LabelId],
) -> Result<(ClauseIr, IrPaths), CompileFault> {
    compile_instance_conjuncts(program, instance, None, bodies, columns)
}

/// The IR of a keyed input's body at `instance`: the clause
/// [`compile_instance_body`] gives, joined with `key`, the rows of the key
/// clause with its paths at the key's labels `key_labels`, which are bound in the body, and
/// are columns of the relation where `columns` holds them.
pub fn compile_keyed_body(
    program: &CheckedProgram,
    instance: &NodePath,
    key: (KeyRead, IrPaths, &[LabelId]),
    body: (&Body, NodePath),
    columns: &[LabelId],
) -> Result<(ClauseIr, IrPaths), CompileFault> {
    compile_instance_conjuncts(program, instance, Some(key), &[body], columns)
}

/// Compile a body in a context that supplies its ambient `given` labels.
/// The context is a separate relation projected to exactly those labels:
/// its local witnesses must not become bindings in the nested body. A
/// body that mentions no ambient label needs no context read.
pub fn compile_ambient_body(
    program: &CheckedProgram,
    form: &NodePath,
    context: &[(&Body, NodePath)],
    given: &[LabelId],
    body: (&Body, NodePath),
    columns: &[LabelId],
) -> Result<ClauseIr, CompileFault> {
    let used = crate::safety::body_labels(body.0);
    if !given.iter().any(|label| used.contains(label)) {
        return compile_instance_body(program, form, &[body], columns);
    }
    let (clause, paths) = compile_instance_pathed(program, form, context, given)?;
    let key = KeyRead { form: form.clone(), clause };
    compile_keyed_body(program, form, (key, paths, given), body, columns).map(|(clause, _)| clause)
}

/// The IR of the instance bodies `bodies`, as [`compile_instance_body`] and
/// [`compile_keyed_body`] give it.
fn compile_instance_conjuncts(
    program: &CheckedProgram,
    instance: &NodePath,
    key: Option<(KeyRead, IrPaths, &[LabelId])>,
    bodies: &[(&Body, NodePath)],
    columns: &[LabelId],
) -> Result<(ClauseIr, IrPaths), CompileFault> {
    let conjuncts = bodies
        .iter()
        .flat_map(|(body, path)| body.conjuncts.iter().zip(0u32..).map(|(conjunct, index)| (conjunct, path.child(index))))
        .collect();
    compile_query(program, instance, key, conjuncts, columns)
}

/// The types of the labels of the scope that holds the labels of the form
/// at `form`.
pub fn label_types<'p>(program: &'p CheckedProgram, form: &NodePath) -> &'p FormTypes {
    form_types(program, &scope_of(program, form))
}

/// The IR of `conjuncts`, each with its path, of the form at `form`, whose
/// relation's columns are those of `columns` that the conjuncts hold.
/// Refuses the conjuncts where they leave a label unbound.
pub fn compile_safe(
    program: &CheckedProgram,
    form: &NodePath,
    conjuncts: Vec<(&Conjunct, NodePath)>,
    columns: &[LabelId],
) -> Result<(ClauseIr, IrPaths), CompileFault> {
    compile_query(program, form, None, conjuncts, columns)
}

/// Compile native-path query conjuncts with an optional projected INIT key.
/// Body views and ordinary safe queries share the binding/type compiler.
pub fn compile_query(
    program: &CheckedProgram,
    form: &NodePath,
    key: Option<(KeyRead, IrPaths, &[LabelId])>,
    conjuncts: Vec<(&Conjunct, NodePath)>,
    columns: &[LabelId],
) -> Result<(ClauseIr, IrPaths), CompileFault> {
    compile_mapped(program, form, key, conjuncts, columns, NodeOrder::Written).map(|mapped| (mapped.clause, mapped.paths))
}

/// What [`compile_mapped`] gives.
struct Mapped {
    clause: ClauseIr,
    paths: IrPaths,
    /// The index in the conjuncts of the one that each node compiles.
    of_node: Vec<usize>,
    /// The label of each column of the clause.
    columns: Box<[LabelId]>,
}

/// The IR of `conjuncts`, as [`compile_safe`] gives it, with the index in
/// `conjuncts` of the conjunct that each node compiles and the label of
/// each column. A `key` is a node that precedes the conjuncts, an atom of
/// the key clause's rows at the labels, which it binds.
fn compile_mapped(
    program: &CheckedProgram,
    form: &NodePath,
    key: Option<(KeyRead, IrPaths, &[LabelId])>,
    conjuncts: Vec<(&Conjunct, NodePath)>,
    columns: &[LabelId],
    order: NodeOrder,
) -> Result<Mapped, CompileFault> {
    let scope = scope_of(program, form);
    let types = form_types(program, &scope);
    let subset = Body { conjuncts: conjuncts.iter().map(|(conjunct, _)| (*conjunct).clone()).collect() };
    let registry = Registry::get();
    let key_labels: &[LabelId] = key.as_ref().map_or(&[], |(_, _, labels)| labels);
    let bound = crate::safety::bound_labels(
        &subset.conjuncts.iter().collect::<Vec<_>>(),
        &key_labels.iter().copied().collect(),
        &StableHashSet::default(),
        &|atom| atom_modes(registry, atom),
        &|label| types.label(label).cloned(),
    );
    let mut held = crate::safety::body_labels(&subset);
    held.extend(key_labels.iter().copied());
    let mut unbound_labels: Vec<LabelId> = held.iter().copied().filter(|label| !bound.contains(label)).collect();
    if !unbound_labels.is_empty() {
        unbound_labels.sort_by_key(|label| label.0);
        return Err(CompileFault::Unbound { labels: unbound_labels.into() });
    }
    let compiled = Compiled {
        conjuncts: conjuncts.iter().map(|(_, path)| path.clone()).collect(),
        columns: columns.into(),
    };
    let mut builder = IrBuilder::new(program, scope, Rc::new(compiled))?;
    builder.canonical_order = order == NodeOrder::Canonical;
    let mut of_node = Vec::new();
    if let Some((read, key_paths, labels)) = key {
        let arguments = labels.iter().zip(0u16..).map(|(&label, column)| (ColumnIndex(column), Argument::Variable(builder.variable(label)))).collect();
        builder.push_first(IrNode::Atom(RelationAtom { source: AtomSource::Key(Box::new(read)), train_only: false, arguments: Arguments(arguments) }), NodePaths::Key(Box::new(key_paths)));
        of_node.push(0);
    }
    for (at, (conjunct, path)) in conjuncts.iter().enumerate() {
        builder.conjunct(conjunct, path)?;
        of_node.resize(builder.nodes.len(), at);
    }
    let labels: Box<[LabelId]> = columns.iter().copied().filter(|label| held.contains(label)).collect();
    let column_variables = labels.iter().map(|&label| builder.variable(label)).collect();
    let (clause, paths) = builder.finish(column_variables);
    let of_node = if order == NodeOrder::Canonical { clause.written.iter().map(|&node| of_node[node as usize]).collect() } else { of_node };
    Ok(Mapped { clause, paths, of_node, columns: labels })
}

/// The IR of the clause at `clause`, a form of `program`: the clause's body,
/// or the body of an instance's input. The relation's columns are the
/// labels the form keeps, in the order of its relation's columns.
pub fn compile_clause(program: &CheckedProgram, clause: &NodePath) -> Result<ClauseIr, CompileFault> {
    let (body, _, _) = form_body(program, clause);
    let kept: Vec<u32> = (0..body.conjuncts.len() as u32).collect();
    compile_conjuncts(program, clause, &kept)
}
