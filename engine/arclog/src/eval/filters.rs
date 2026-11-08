//! The filters of a clause: the compilation of `NOT`, `ALL`, `IF` and `OR`
//! into the IR, the probe of a filter, and the early stop of a search over
//! local labels.
//!
//! A negated atom, an `ALL`'s counterexample relation and the negated test
//! of an `IF`'s else branch are filters: each is probed once its outer
//! variables are bound, with those bindings only, and none is evaluated
//! alone, since a test that reads an algebra relation through outer labels
//! is no finite relation.
//!
//! Inside a filter or an `OR` branch, a label that the scope does not
//! export is local: a variable of the clause's body that none of its
//! columns holds. The early stop of a search over local variables is that of
//! [`super::join::join_at`].
//!
//! A variable of a body this file compiles is the variable of its label in
//! the enclosing form, so a filter's body and the clause that probes it
//! name one label by one variable.

use std::collections::BTreeSet;

use super::ReachedBound;
use super::ir::{CompileFault, Filter, IrBuilder, IrNode, IrPaths, NodePaths, Union, Variable};
use super::join::{Budget, JoinInputs};
use super::plan::VariableOrder;
use crate::hash::StableHashSet;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Body, Conjunct, LabelId, LabelUse, Negated, Node};
use crate::registry::Registry;
use crate::terms::TermId;

/// Compiles a `NOT` at `path` into a [`super::ir::IrNode::Not`] of
/// `builder`'s clause.
pub fn compile_not(builder: &mut IrBuilder<'_>, negated: &Negated, path: &NodePath) -> Result<(), CompileFault> {
    let mut inner = nested(builder);
    match negated {
        Negated::Atom(atom) => inner.conjunct(&Conjunct::Atom(atom.clone()), path)?,
        Negated::Form(form) => inner.conjunct(form, &path.child(0))?,
    }
    let outer = variables_of(builder, &outer_labels(builder, path));
    let (filter, paths) = filter(outer, inner);
    builder.push(IrNode::Not(filter), NodePaths::Filter(Box::new(paths)));
    Ok(())
}

/// Compiles an `ALL` at `path` into the
/// [`super::ir::IrNode::Counterexample`] of
/// `docs/arclog/arclog.md#universal`: a member of `domain` that fails
/// `body`. The existence test, that the domain has a member, is a `NOT` of
/// a `NOT` of the domain.
pub fn compile_all(
    builder: &mut IrBuilder<'_>,
    domain: &Node<Body>,
    body: &Node<Body>,
    path: &NodePath,
) -> Result<(), CompileFault> {
    let (domain_path, body_path) = (path.child(0), path.child(1));
    let around = outer_labels(builder, path);
    let mut fails = nested(builder);
    fails.body(body.value(), &body_path)?;
    let (fails, fails_paths) = filter(variables_of(builder, &outer_labels(builder, &body_path)), fails);
    let mut counterexample = nested(builder);
    counterexample.body(domain.value(), &domain_path)?;
    counterexample.push(IrNode::Not(fails), NodePaths::Filter(Box::new(fails_paths)));
    let mut members = nested(builder);
    members.body(domain.value(), &domain_path)?;
    let domain_outer = variables_of(builder, &outer_of(domain.value(), &around));
    let mut empty = nested(builder);
    let (members, members_paths) = filter(domain_outer.clone(), members);
    empty.push(IrNode::Not(members), NodePaths::Filter(Box::new(members_paths)));
    let (empty, empty_paths) = filter(domain_outer, empty);
    builder.push(IrNode::Not(empty), NodePaths::Filter(Box::new(empty_paths)));
    let outer = variables_of(builder, &around);
    let (counterexample, counterexample_paths) = filter(outer, counterexample);
    builder.push(IrNode::Counterexample(counterexample), NodePaths::Filter(Box::new(counterexample_paths)));
    Ok(())
}

/// Compiles an `IF` at `path` into a [`super::ir::IrNode::Or`] of the two
/// clauses of `docs/arclog/arclog.md#conditional`: the test with the then,
/// and the else with the test negated.
pub fn compile_if(
    builder: &mut IrBuilder<'_>,
    test: &Node<Body>,
    then: &Node<Body>,
    otherwise: &Node<Body>,
    path: &NodePath,
) -> Result<(), CompileFault> {
    let (test_path, then_path, else_path) = (path.child(0), path.child(1), path.child(2));
    let around = outer_labels(builder, path);
    let mut negated = nested(builder);
    negated.body(test.value(), &test_path)?;
    let test_outer = variables_of(builder, &outer_of(test.value(), &around));
    let (test_filter, test_paths) = filter(test_outer, negated);
    let branches = [
        Branch { lists: vec![(test, test_path.clone()), (then, then_path.clone())], negated: None },
        Branch { lists: vec![(otherwise, else_path.clone())], negated: Some((test_filter, test_paths, test.value())) },
    ];
    let made = exported_labels(then.value(), &[otherwise.value()]);
    compile_union(builder, &branches, around, made)
}

/// Compiles an `OR` at `path` into a [`super::ir::IrNode::Or`], each branch
/// a clause that binds the variables the `OR` exports.
pub fn compile_or(builder: &mut IrBuilder<'_>, branches: &[Node<Body>], path: &NodePath) -> Result<(), CompileFault> {
    let paths: Vec<NodePath> = (0..branches.len() as u32).map(|index| path.child(index)).collect();
    let around = outer_labels(builder, path);
    let later: Vec<&Body> = branches[1..].iter().map(Node::value).collect();
    let made = exported_labels(branches[0].value(), &later);
    let branches: Vec<Branch<'_>> =
        branches.iter().zip(&paths).map(|(branch, path)| Branch { lists: vec![(branch, path.clone())], negated: None }).collect();
    compile_union(builder, &branches, around, made)
}

/// One branch of a union: its lists of conjuncts, each with its path, and
/// the negated test of an `IF`'s else, with the paths of its nodes and the
/// test.
struct Branch<'b> {
    lists: Vec<(&'b Node<Body>, NodePath)>,
    negated: Option<(Filter, IrPaths, &'b Body)>,
}

/// Adds to `builder`'s clause the union of `branches`. `around` holds the
/// labels of the union that stand outside it, and `made` the labels made in
/// its first branch that every later branch mentions. The union exports each
/// of those labels that every branch binds from the others, and a
/// branch's columns are its labels among them.
fn compile_union(
    builder: &mut IrBuilder<'_>,
    branches: &[Branch<'_>],
    around: BTreeSet<u32>,
    made: BTreeSet<u32>,
) -> Result<(), CompileFault> {
    let shared: BTreeSet<u32> = around.union(&made).copied().collect();
    let mut held = Vec::with_capacity(branches.len());
    let mut per_branch = Vec::with_capacity(branches.len());
    for branch in branches {
        let mut labels = BTreeSet::new();
        for (list, _) in &branch.lists {
            labels.extend(labels_of(list.value()));
        }
        if let Some((_, _, test)) = &branch.negated {
            labels.extend(outer_of(test, &around));
        }
        let body = Body { conjuncts: branch.lists.iter().flat_map(|(list, _)| list.value().conjuncts.iter().cloned()).collect() };
        let exports: StableHashSet<LabelId> = shared.iter().copied().filter(|&label| binds(builder, &body, &shared, label)).map(LabelId).collect();
        held.push(labels);
        per_branch.push(exports);
    }
    let exported: BTreeSet<u32> = crate::safety::common_to_all(per_branch).into_iter().map(|label| label.0).collect();
    // Only context variables and actual exports cross a branch boundary.
    // Syntactically made labels that another branch merely mentions remain
    // local; projecting them would ask the join to enumerate an unbound value.
    let shared: BTreeSet<u32> = around.union(&exported).copied().collect();
    let mut clauses = Vec::with_capacity(branches.len());
    let mut branch_paths: Vec<IrPaths> = Vec::with_capacity(branches.len());
    for (branch, labels) in branches.iter().zip(&held) {
        // Nested unions see this branch's lexical context, not sibling
        // branches elsewhere in the top-level form. Reusing the top-level
        // context incorrectly turns a sibling's local into an outer input.
        let compiled = super::ir::Compiled {
            conjuncts: branch.lists.iter().flat_map(|(list,path)|
                (0..list.value().conjuncts.len()).map(|i|path.child(i as u32))).collect(),
            columns: labels.intersection(&shared).copied().map(LabelId).collect(),
        };
        let mut clause = IrBuilder::new(builder.program,builder.form.clone(),std::rc::Rc::new(compiled));
        clause.canonical_order = builder.canonical_order;
        for (list, path) in &branch.lists {
            clause.body(list.value(), path)?;
        }
        if let Some((test, test_paths, _)) = &branch.negated {
            clause.push(IrNode::Not(test.clone()), NodePaths::Filter(Box::new(test_paths.clone())));
        }
        let columns = variables_of(builder, &labels.intersection(&shared).copied().collect());
        let (clause, paths) = clause.finish(columns);
        clauses.push(clause);
        branch_paths.push(paths);
    }
    let exported = variables_of(builder, &exported);
    // The union is searched branch by branch in the canonical order of the
    // branches' paths, which the order of the branches as written does not give.
    let keys: Vec<Vec<u32>> = branches.iter().map(|branch| builder.key_of(&branch.lists[0].1)).collect();
    let mut canonical: Vec<u32> = (0..branches.len() as u32).collect();
    canonical.sort_by(|&a, &b| keys[a as usize].cmp(&keys[b as usize]));
    builder.push(IrNode::Or(Union { exported, branches: clauses.into(), canonical: canonical.into() }), NodePaths::Branches(branch_paths.into()));
    Ok(())
}

/// Whether `body`, the conjuncts of one branch, binds `label` where every
/// other label of `shared` is bound, as
/// [`crate::safety::bound_labels`] gives the bound labels.
fn binds(builder: &IrBuilder<'_>, body: &Body, shared: &BTreeSet<u32>, label: u32) -> bool {
    let given: StableHashSet<LabelId> = shared.iter().filter(|&&other| other != label).map(|&other| LabelId(other)).collect();
    let outside: StableHashSet<LabelId> = shared.iter().map(|&other| LabelId(other)).collect();
    let types = builder.program.types.form(&builder.form).expect("the label types of each scope of a checked program");
    let registry = Registry::get();
    let modes = |atom: &crate::program::Atom| super::ir::atom_modes(registry, atom);
    let types = |label: LabelId| types.label(label).cloned();
    crate::safety::bound_labels(&body.conjuncts.iter().collect::<Vec<_>>(), &given, &outside, &modes, &types).contains(&LabelId(label))
}

/// The conjunct kinds this file compiles, for the dispatch of
/// [`IrBuilder::body`]: whether `conjunct` is a `NOT`, an `ALL`, an `IF` or
/// an `OR`.
pub fn is_filter_form(conjunct: &Conjunct) -> bool {
    matches!(conjunct, Conjunct::Not(_) | Conjunct::All { .. } | Conjunct::If { .. } | Conjunct::Or(_))
}

/// Whether `filter` holds a binding at `outer`, the values of its outer
/// variables in the order of [`Filter::outer`], over `inputs`, the inputs
/// of its body, searched in `order` with the early stop on local
/// variables, in the evaluation whose memo is `memo`.
pub fn probe(
    memo: &super::join::SearchMemo,
    filter: &Filter,
    outer: &[TermId],
    order: &VariableOrder,
    inputs: &JoinInputs,
    registry: &crate::registry::Registry,
    budget: &mut Budget<'_>,
) -> Result<bool, ReachedBound> {
    let bound: Vec<(Variable, TermId)> = filter.outer.iter().copied().zip(outer.iter().copied()).collect();
    let relation = super::join::join_in(memo, &filter.body, order, inputs, registry, &bound, budget)?;
    Ok(!relation.is_empty())
}

/// A builder of a clause nested in `builder`'s, over the variables of the
/// same form.
fn nested<'a>(builder: &IrBuilder<'a>) -> IrBuilder<'a> {
    let mut inner = IrBuilder::new(builder.program, builder.form.clone(), builder.compiled.clone());
    inner.canonical_order = builder.canonical_order;
    inner
}

/// The filter over `outer` whose body is the clause of `body`, a relation
/// with no column, with the paths of the clause's nodes.
fn filter(outer: Box<[Variable]>, body: IrBuilder<'_>) -> (Filter, IrPaths) {
    let (clause, paths) = body.finish(Box::new([]));
    (Filter { outer, body: Box::new(clause) }, paths)
}

/// The labels that stand at `path` and also outside it, in the conjuncts
/// that the compile of `builder` takes, at any depth, or among the columns
/// of the relation it gives: those a body at `path` reads from the clause
/// around it.
fn outer_labels(builder: &IrBuilder<'_>, path: &NodePath) -> BTreeSet<u32> {
    let root = NodeRef::Program(builder.program.program.program.value());
    let mut inside = BTreeSet::new();
    let mut outside: BTreeSet<u32> = builder.compiled.columns.iter().map(|label| label.0).collect();
    for conjunct in builder.compiled.conjuncts.iter() {
        each_label(node_at(root, conjunct).expect("the path of a conjunct of the program"), conjunct, &mut |at, label| {
            let set = if at.0.starts_with(&path.0) { &mut inside } else { &mut outside };
            set.insert(label.0);
        });
    }
    inside.intersection(&outside).copied().collect()
}

/// The labels of `body` that also stand outside it, of `around`, the
/// labels [`outer_labels`] gives for the path that encloses `body`.
fn outer_of(body: &Body, around: &BTreeSet<u32>) -> BTreeSet<u32> {
    labels_of(body).intersection(around).copied().collect()
}

/// The labels that stand in `body`, at any depth.
fn labels_of(body: &Body) -> BTreeSet<u32> {
    crate::safety::body_labels(body).into_iter().map(|label| label.0).collect()
}

/// The labels that a form with its first list `first` and its later lists
/// `later` exports, as [`crate::read::columns::exports`] gives them.
fn exported_labels(first: &Body, later: &[&Body]) -> BTreeSet<u32> {
    let mut labels = Vec::new();
    crate::read::columns::exports(first, later, &mut labels);
    labels.into_iter().map(|label| label.0).collect()
}

/// The variables of `labels`, in the order of the variables.
fn variables_of(builder: &mut IrBuilder<'_>, labels: &BTreeSet<u32>) -> Box<[Variable]> {
    let mut variables: Vec<Variable> = labels.iter().map(|&label| builder.variable(LabelId(label))).collect();
    variables.sort_by_key(|variable| variable.0);
    variables.into()
}

/// Calls `visit` on each label that stands in `node` at `at`, at any depth,
/// with the path where it stands.
fn each_label(node: NodeRef<'_>, at: &NodePath, visit: &mut dyn FnMut(&NodePath, LabelId)) {
    match node {
        NodeRef::Label(LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label)) => visit(at, *label),
        NodeRef::Conjunct(Conjunct::Constraint(constraint)) => {
            visit(at, constraint.first.label);
            if let crate::program::Operand::Label(second) = constraint.second {
                visit(at, second.label);
            }
        }
        _ => {}
    }
    for (child, index) in node.children().into_iter().zip(0u32..) {
        each_label(child, &at.child(index), visit);
    }
}
