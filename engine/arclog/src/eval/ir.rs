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
}

/// An atom of a relation with rows: a fact relation or a relation of the
/// dependency graph.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct RelationAtom {
    pub source: AtomSource,
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
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Union {
    pub exported: Box<[Variable]>,
    pub branches: Box<[ClauseIr]>,
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
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct ClauseIr {
    pub variables: Box<[VariableInfo]>,
    pub nodes: Box<[IrNode]>,
    pub columns: Box<[Variable]>,
}

/// A body that the IR cannot hold: a grounded subset of a body is
/// required, and a subset that leaves a label ungrounded is refused with
/// those labels; a form whose scope holds a label that the checked program
/// gives no type is refused with that label.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum CompileFault {
    Ungrounded { labels: Box<[LabelId]> },
    Untyped { label: LabelId },
}

/// The state of a compilation of one body: the variables given so far and
/// the nodes compiled so far.
#[derive(Debug)]
pub struct IrBuilder<'a> {
    pub program: &'a CheckedProgram,
    /// The path of the form whose body is compiled, whose label types the
    /// variables take.
    pub form: NodePath,
    /// The canonical order of the top-level form that holds `form`.
    order: CanonicalOrder,
    variables: Vec<VariableInfo>,
    nodes: Vec<IrNode>,
}

impl<'a> IrBuilder<'a> {
    /// A builder over the body of the form at `form` of `program`, or the
    /// fault of a label of the form's scope that `program` gives no type.
    pub fn new(program: &'a CheckedProgram, form: NodePath) -> Result<Self, CompileFault> {
        let (first, scope) = form.0.split_first().expect("the path of a form of the program");
        let top = &program.program.program.value().forms[first.0 as usize];
        let order = CanonicalOrder::of(top, &mut SearchBudget::new());
        let scope = NodePath(scope.into());
        let types = form_types(program, &form);
        let labels = order.label_scopes().into_iter().find(|(path, _)| *path == scope).map(|(_, labels)| labels.to_vec());
        let mut variables = vec![None; labels.as_ref().map_or(0, Vec::len)];
        for (label, position) in labels.into_iter().flatten() {
            let ty = types.label(label).ok_or(CompileFault::Untyped { label })?.clone();
            variables[position as usize] = Some(VariableInfo { ty });
        }
        let variables = variables.into_iter().map(|info| info.expect("a label at each canonical position")).collect();
        Ok(IrBuilder { program, form, order, variables, nodes: Vec::new() })
    }

    /// The variable of `label`: its canonical position in the form's scope.
    pub fn variable(&mut self, label: LabelId) -> Variable {
        let scope = NodePath(self.form.0[1..].into());
        Variable(u16::try_from(self.order.canonical_label(&scope, label)).expect("fewer than 2^16 labels in a scope"))
    }

    /// Adds `node` to the clause.
    pub fn push(&mut self, node: IrNode) {
        self.nodes.push(node);
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

    /// Compiles one conjunct at `path`.
    pub(super) fn conjunct(&mut self, conjunct: &Conjunct, path: &NodePath) -> Result<(), CompileFault> {
        match conjunct {
            Conjunct::Atom(atom) => {
                let node = self.atom(atom.value(), path);
                self.push(node);
            }
            Conjunct::Constraint(constraint) => {
                let first = self.variable(constraint.first.label);
                let second = match constraint.second {
                    crate::program::Operand::Label(label) => Operand::Variable(self.variable(label.label)),
                    crate::program::Operand::Zero => Operand::Zero,
                };
                self.push(IrNode::Comparison(Comparison { op: constraint.op, first, second, binds_first: constraint.first.fresh }));
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
            return IrNode::Atom(RelationAtom { source: AtomSource::Fact(*fact), arguments });
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
        IrNode::Atom(RelationAtom { source, arguments })
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

    /// The clause, whose relation holds `columns`.
    pub fn finish(self, columns: Box<[Variable]>) -> ClauseIr {
        ClauseIr { variables: self.variables.into(), nodes: self.nodes.into(), columns }
    }
}

/// The types of the labels of the scope at `form`.
fn form_types<'p>(program: &'p CheckedProgram, form: &NodePath) -> &'p FormTypes {
    program.types.form(form).expect("the label types of each scope of a checked program")
}

/// The modes of the relation `atom` reads: an algebra relation's or a
/// relation macro's, and none for every other relation.
pub(crate) fn atom_modes<'r>(registry: &'r Registry, atom: &Atom) -> &'r [Mode] {
    let RelationRef::Lib(name) = &atom.relation else { return &[] };
    registry.algebra_relation(name).map_or(&[], |relation| &relation.modes)
}

/// The path of the form whose label scope holds the labels of the form at
/// `path`: the innermost label scope of the canonical labeling,
/// [`CanonicalOrder::label_scopes`], whose form holds it.
fn scope_of(program: &CheckedProgram, path: &NodePath) -> NodePath {
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
            (input.body.value(), clause.child(input.head.len() as u32), labels)
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
/// Where the kept conjuncts leave a label ungrounded, as
/// [`crate::grounding::grounded_labels`] gives grounding, this refuses them
/// with those labels.
pub fn compile_conjuncts(program: &CheckedProgram, clause: &NodePath, kept: &[u32]) -> Result<ClauseIr, CompileFault> {
    let (body, body_path, columns) = form_body(program, clause);
    let conjuncts = kept.iter().map(|&index| (&body.conjuncts[index as usize], body_path.child(index))).collect();
    compile_grounded(program, clause, conjuncts, &columns)
}

/// The IR of the bodies `bodies` of the `INIT` form at `instance`, each with
/// its path, as one clause whose relation's columns are the labels
/// `columns`, in their order: the key body alone, whose columns are the
/// key's labels, or a keyed input's body joined with the key body, whose
/// columns are the key's labels and then the input's. A label of `columns`
/// that no body holds is no column of the relation. Where the bodies leave
/// a label ungrounded, this refuses them with those labels, as
/// [`compile_conjuncts`] does.
pub fn compile_instance_body(
    program: &CheckedProgram,
    instance: &NodePath,
    bodies: &[(&Body, NodePath)],
    columns: &[LabelId],
) -> Result<ClauseIr, CompileFault> {
    let conjuncts = bodies
        .iter()
        .flat_map(|(body, path)| body.conjuncts.iter().zip(0u32..).map(|(conjunct, index)| (conjunct, path.child(index))))
        .collect();
    compile_grounded(program, instance, conjuncts, columns)
}

/// The types of the labels of the scope that holds the labels of the form
/// at `form`.
pub fn label_types<'p>(program: &'p CheckedProgram, form: &NodePath) -> &'p FormTypes {
    form_types(program, &scope_of(program, form))
}

/// The IR of `conjuncts`, each with its path, of the form at `form`, whose
/// relation's columns are those of `columns` that the conjuncts hold.
/// Refuses the conjuncts where they leave a label ungrounded.
pub fn compile_grounded(
    program: &CheckedProgram,
    form: &NodePath,
    conjuncts: Vec<(&Conjunct, NodePath)>,
    columns: &[LabelId],
) -> Result<ClauseIr, CompileFault> {
    let scope = scope_of(program, form);
    let types = form_types(program, &scope);
    let subset = Body { conjuncts: conjuncts.iter().map(|(conjunct, _)| (*conjunct).clone()).collect() };
    let registry = Registry::get();
    let grounded = crate::grounding::grounded_labels(
        &subset,
        &StableHashSet::default(),
        &StableHashSet::default(),
        &|atom| atom_modes(registry, atom),
        &|label| types.label(label).cloned(),
    );
    let held = crate::grounding::body_labels(&subset);
    let mut ungrounded: Vec<LabelId> = held.iter().copied().filter(|label| !grounded.contains(label)).collect();
    if !ungrounded.is_empty() {
        ungrounded.sort_by_key(|label| label.0);
        return Err(CompileFault::Ungrounded { labels: ungrounded.into() });
    }
    let mut builder = IrBuilder::new(program, scope)?;
    for (conjunct, path) in &conjuncts {
        builder.conjunct(conjunct, path)?;
    }
    let columns = columns.iter().copied().filter(|label| held.contains(label)).map(|label| builder.variable(label)).collect();
    Ok(builder.finish(columns))
}

/// The IR of the clause at `clause`, a form of `program`: the clause's body,
/// or the body of an instance's input. The relation's columns are the
/// labels the form keeps, in the order of its relation's columns.
pub fn compile_clause(program: &CheckedProgram, clause: &NodePath) -> Result<ClauseIr, CompileFault> {
    let (body, _, _) = form_body(program, clause);
    let kept: Vec<u32> = (0..body.conjuncts.len() as u32).collect();
    compile_conjuncts(program, clause, &kept)
}
