//! The clause IR, the evaluator's form of a body after name resolution and
//! macro expansion: a conjunctive query with filters and unions, over
//! resolved relations, and the compilation of a body's positive
//! conjunctive part into it.
//!
//! A variable of the IR is a label of the body at its canonical position,
//! so two bodies of equal resolved content compile to equal IR, and an
//! order over variables that breaks ties by their index breaks them by
//! content. [`crate::eval::filters`] compiles `NOT`, `ALL`, `IF` and `OR`
//! through [`IrBuilder`].

#![allow(unused_variables, dead_code)]

use crate::check::CheckedProgram;
use crate::program::path::NodePath;
use crate::program::{Body, ConstraintOp, FactRelation, LabelId, ProgramRelation};
use crate::registry::LibName;
use crate::relations::ColumnIndex;
use crate::terms::TermId;
use crate::types::{GraphRelation, ValueType};

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

/// An `IF`: its test, its then and its else, each a clause over the outer
/// variables, as `docs/arclog/arclog.md#conditional` gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Conditional {
    pub test: Filter,
    pub then: Box<ClauseIr>,
    pub otherwise: Box<ClauseIr>,
}

/// An `OR`: its branches, each a clause, and the variables it exports to
/// the enclosing clause, which every branch binds.
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
    If(Conditional),
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
/// those labels.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum CompileFault {
    Ungrounded { labels: Box<[LabelId]> },
}

/// The state of a compilation of one body: the variables given so far and
/// the nodes compiled so far.
#[derive(Debug)]
pub struct IrBuilder<'a> {
    pub program: &'a CheckedProgram,
    /// The path of the form whose body is compiled, whose label types the
    /// variables take.
    pub form: NodePath,
    variables: Vec<VariableInfo>,
    nodes: Vec<IrNode>,
}

impl<'a> IrBuilder<'a> {
    /// A builder over the body of the form at `form` of `program`.
    pub fn new(program: &'a CheckedProgram, form: NodePath) -> Self {
        IrBuilder { program, form, variables: Vec::new(), nodes: Vec::new() }
    }

    /// The variable of `label`, given on first use.
    pub fn variable(&mut self, label: LabelId) -> Variable {
        todo!()
    }

    /// Adds `node` to the clause.
    pub fn push(&mut self, node: IrNode) {
        self.nodes.push(node);
    }

    /// Compiles the conjuncts of `body` at `path` into the clause: its atoms
    /// and its comparisons here, and each `NOT`, `ALL`, `IF` and `OR`
    /// through [`crate::eval::filters`].
    pub fn body(&mut self, body: &Body, path: &NodePath) -> Result<(), CompileFault> {
        todo!()
    }

    /// The clause, whose relation holds `columns`.
    pub fn finish(self, columns: Box<[Variable]>) -> ClauseIr {
        todo!()
    }
}

/// The IR of the clause at `clause`, a form of `program`: the clause's body,
/// or the body of an instance's input. The relation's columns are the
/// labels the form keeps, in the order of its relation's columns.
pub fn compile_clause(program: &CheckedProgram, clause: &NodePath) -> Result<ClauseIr, CompileFault> {
    todo!()
}
