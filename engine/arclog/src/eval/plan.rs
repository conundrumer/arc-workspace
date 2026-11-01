//! The variable order of a clause, which generic join binds the variables
//! in.
//!
//! The order is a function of the clause's IR and the sizes of the
//! relations it reads, so a body of equal content over relations of equal
//! ids has one plan. It is the order of least estimated bindings. A choice
//! of the order is a variable that an atom binds, estimated at the least,
//! over the atoms that bind it, of the atom's row count divided by the
//! domains of the atom's other variables that are placed before the choice,
//! and at least 1, or a variable that a union exports
//! and no atom or comparison binds, estimated at the sum over the union's
//! branches of the estimate of the variable in the branch, and chosen only
//! where the union grounds at the placed variables: each column of its
//! branches that it does not export is placed or has a finite orientation
//! domain, and each branch, with its
//! placed columns bound, grounds every variable it holds. The domain of a
//! variable is the row count of the smallest atom that binds it, or the size
//! of its orientation type where that is less, so a variable that an atom
//! gives from placed variables, such as a remainder that an atom keys by a
//! cell and a direction, has a small estimate once they are placed. A
//! variable that an algebra relation or an `=` places costs nothing, and the
//! cost of a sequence of choices is the sum over its choices of the product
//! of the estimates up to that choice. Each choice is followed by the outputs
//! of each algebra relation whose mode the placed variables satisfy, and by
//! each variable an `=` binds from a placed one. A tie in cost goes to the
//! sequence of the smaller estimates with no variable placed, then of the
//! canonical positions. A clause with more than 12 choices takes next the
//! choice of least estimate at the variables placed, a tie going to the
//! smaller estimate with no variable placed, then to the canonical position,
//! each export of a union that no atom or comparison binds once its union
//! grounds. Where no variable left meets
//! that rule, as where a union's branch reads a variable that only another
//! union's exports ground, the order places the first export of a union that
//! grounds with the nodes it leaves out: each export of the union, and each variable
//! that a kept node holds, is grounded in every branch, and a node is left out
//! where it holds a column that is neither placed, grounded nor of an
//! orientation type. Where no union grounds in that way either, as where a
//! branch's `=` equates an export of no orientation type with a label of an
//! orientation type, the order places the first export of such a union, and
//! a variable that only an algebra relation gives values waits for a mode of
//! that relation.

use super::join::node_variables;
use super::ir::{Argument, Arguments, ClauseIr, IrNode, Operand, Union, Variable};
use crate::program::ConstraintOp;
use crate::registry::{AlgebraRelation, LibName, Registry};
use crate::algebra::geometry::{domain, orientation_domain};

/// The most choices the order searches subsets of; past it the order places
/// the choices by estimate.
const SUBSET_BOUND: usize = 12;

/// The order the join binds a clause's variables in, each variable once.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct VariableOrder(pub Box<[Variable]>);

/// What the order knows of the relations a node of a clause reads.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum NodeSize {
    /// No relation with rows, such as a comparison or an algebra relation's
    /// atom.
    Unread,
    /// The count of rows of an atom's relation.
    Rows(u64),
    /// The sizes of the node's own clauses: a filter's body, or a union's
    /// branches, in the node's order.
    Clauses(Box<[RelationSizes]>),
}

/// The sizes of the relations each node of a clause reads, by the node's
/// index in [`ClauseIr::nodes`].
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct RelationSizes(pub Box<[NodeSize]>);

/// The variable order of `clause` over relations of `sizes`: the sequence of
/// choices of least estimated bindings, each followed by its closure, as the
/// module doc gives. Each variable that an algebra relation binds stands
/// after the inputs of the mode that binds it, and each variable that a union
/// exports, and no atom or comparison binds, once that union grounds at the
/// variables placed before it, as the module doc gives, so the order binds
/// every variable that the clause binds.
///
/// The order holds each variable that a node of the clause holds
/// ([`node_variables`]), other than `outer`'s, and a variable that no node
/// binds stands after the ones that nodes bind; a variable that stands only
/// in a filter's body is the filter's own. A variable that an `=` binds from
/// another stands directly after that other, as an algebra relation's output
/// does.
///
/// `outer` holds the variables of `clause` that its caller binds before the
/// join. They count as bound, so the inputs of a mode they satisfy are
/// held, and they stand in no place of the order, as the join drops a bound
/// variable from it.
pub fn variable_order(clause: &ClauseIr, sizes: &RelationSizes, outer: &[Variable]) -> VariableOrder {
    let count = clause.variables.len();
    let mut bound = vec![false; count];
    for variable in clause.nodes.iter().flat_map(bound_variables) {
        bound[usize::from(variable.0)] = true;
    }
    let mut placed = vec![false; count];
    let mut order = Vec::new();
    for variable in outer {
        placed[usize::from(variable.0)] = true;
    }
    follow(clause, &mut placed, &mut order);
    let mut extend = |placed: &mut Vec<bool>, chosen: Variable| {
        place(chosen, placed, &mut Vec::new());
        follow(clause, placed, &mut Vec::new());
    };
    let choices = choices(clause, sizes, &placed, &mut extend);
    let estimates = Estimates::new(clause, sizes);
    let sequence = if (2..=SUBSET_BOUND).contains(&choices.len()) {
        cheapest_sequence(&choices, &estimates, &placed, &mut extend)
    } else {
        sequence_in_order(&choices, &estimates, &placed, &mut extend)
    };
    for variable in sequence {
        place(variable, &mut placed, &mut order);
        follow(clause, &mut placed, &mut order);
    }
    let binders = union_binders(clause);
    let direct = direct_variables(clause);
    let ready = |placed: &[bool]| {
        (0..count).map(|v| Variable(v as u16)).find(|variable| {
            let v = usize::from(variable.0);
            !placed[v] && (direct[v] || binders[v].is_some_and(|(_, union)| grounds(union, placed)))
        })
    };
    while let Some(variable) = ready(&placed) {
        place(variable, &mut placed, &mut order);
        follow(clause, &mut placed, &mut order);
    }
    let mut held = vec![false; count];
    for variable in clause.nodes.iter().flat_map(node_variables) {
        held[usize::from(variable.0)] = true;
    }
    let waiting = mode_waiting(clause, &direct, &binders);
    for wanted in [bound, held] {
        while let Some(variable) = next_left(&wanted, &placed, &binders, &waiting) {
            place(variable, &mut placed, &mut order);
            follow(clause, &mut placed, &mut order);
        }
    }
    VariableOrder(order.into())
}

/// Marks `variable` placed and appends it to `order`, if it was not placed.
fn place(variable: Variable, placed: &mut [bool], order: &mut Vec<Variable>) {
    if !std::mem::replace(&mut placed[usize::from(variable.0)], true) {
        order.push(variable);
    }
}

/// Places, until nothing changes, the outputs of each algebra relation of
/// `clause` whose mode the placed variables satisfy, and each variable an `=`
/// binds from a placed one.
fn follow(clause: &ClauseIr, placed: &mut [bool], order: &mut Vec<Variable>) {
    let registry = Registry::get();
    loop {
        let before = placed.iter().filter(|&&p| p).count();
        for node in clause.nodes.iter() {
            match node {
                IrNode::Lib(atom) => {
                    let relation = algebra_relation(registry, &atom.relation);
                    if mode_holds(relation, &atom.arguments, clause, placed) {
                        let mut outputs: Vec<Variable> = variables_of(&atom.arguments).collect();
                        outputs.sort_by_key(|v| v.0);
                        outputs.into_iter().for_each(|v| place(v, placed, order));
                    }
                }
                IrNode::Comparison(comparison) if comparison.op == ConstraintOp::Eq => match comparison.second {
                    Operand::Zero => place(comparison.first, placed, order),
                    Operand::Variable(second) => {
                        if placed[usize::from(comparison.first.0)] {
                            place(second, placed, order);
                        } else if placed[usize::from(second.0)] {
                            place(comparison.first, placed, order);
                        }
                    }
                },
                _ => {}
            }
        }
        if placed.iter().filter(|&&p| p).count() == before {
            break;
        }
    }
}

/// The first variable of `wanted` that is not placed, in index order, other
/// than one of `waiting` and one that a union binds and does not yet
/// [`grounds`]; where every variable left is of those kinds, the first whose
/// union [`grounds_leaving`], the case of a clause whose unions ground one
/// another's columns; where none is, the first variable left outside
/// `waiting`, the case of a union that grounds at no placement, whose values
/// the join takes from the branches with the nodes they leave out, and which
/// the union's check then holds to the whole branches; and otherwise the
/// first variable left. The last case is one that no clause which passes the
/// whole-form check reaches. The order holds every variable of `wanted`.
fn next_left(wanted: &[bool], placed: &[bool], binders: &[Option<(usize, &Union)>], waiting: &[bool]) -> Option<Variable> {
    let left = |v: &usize| wanted[*v] && !placed[*v];
    let free = |v: &usize| left(v) && !waiting[*v];
    let ready = |v: &usize, holds: fn(&Union, &[bool]) -> bool| binders[*v].is_none_or(|(_, union)| holds(union, placed));
    (0..wanted.len())
        .filter(free)
        .find(|v| ready(v, grounds))
        .or_else(|| (0..wanted.len()).filter(free).find(|v| ready(v, grounds_leaving)))
        .or_else(|| (0..wanted.len()).find(free))
        .or_else(|| (0..wanted.len()).find(left))
        .map(|v| Variable(v as u16))
}

/// Whether the join has values for each variable only from an algebra
/// relation, by the variable's index: an algebra relation holds it, no atom,
/// comparison or union binds it, and it has no orientation domain. Such a
/// variable takes its place from [`follow`] once a mode of that relation
/// holds, and has no values before that.
fn mode_waiting(clause: &ClauseIr, direct: &[bool], binders: &[Option<(usize, &Union)>]) -> Vec<bool> {
    let mut waiting = vec![false; clause.variables.len()];
    for node in clause.nodes.iter() {
        if let IrNode::Lib(atom) = node {
            for variable in variables_of(&atom.arguments) {
                let v = usize::from(variable.0);
                waiting[v] = !direct[v] && binders[v].is_none() && orientation_domain(&clause.variables[v].ty).is_none();
            }
        }
    }
    waiting
}

/// `order`, the variables that a search of the nodes `nodes` of `clause` binds
/// with `bound` bound before it, with each variable that would have no values
/// at its place moved to the first place where it has them. A variable has
/// values at a place where an atom of `nodes` or of `tries` holds it, a union of
/// `nodes` exports it, it is of an orientation type, an `=` gives it from `0` or
/// from a placed variable, or an algebra relation that holds it has a mode at
/// the placed variables. These are the sources of the search, so where each
/// variable of `order` has values at its place, the result is `order`.
///
/// [`variable_order`] does not see what the search sees: a union that grounds at
/// no placement leaves its variables to [`next_left`], which places a variable
/// that a comparison holds before the mode of an algebra relation gives it, and
/// a search of a branch leaves out nodes ([`kept_nodes`]). A variable that has
/// values at no place keeps the order of the variables left, and the search
/// stops there ([`NoValues`](super::ReachedBound::NoValues)).
pub(super) fn values_first(clause: &ClauseIr, nodes: &[usize], tries: &[&Arguments], order: Vec<Variable>, bound: &[Variable]) -> Vec<Variable> {
    let registry = Registry::get();
    let index = |variable: &Variable| usize::from(variable.0);
    let nodes: Vec<&IrNode> = nodes.iter().map(|&node| &clause.nodes[node]).collect();
    let mut always: Vec<bool> = clause.variables.iter().map(|variable| orientation_domain(&variable.ty).is_some()).collect();
    for arguments in nodes.iter().filter_map(|node| if let IrNode::Atom(atom) = node { Some(&atom.arguments) } else { None }).chain(tries.iter().copied()) {
        variables_of(arguments).for_each(|variable| always[index(&variable)] = true);
    }
    for union in nodes.iter().filter_map(|node| if let IrNode::Or(union) = node { Some(union) } else { None }) {
        union.exported.iter().for_each(|variable| always[index(variable)] = true);
    }
    let gives = |node: &IrNode, variable: Variable, placed: &[bool]| match node {
        IrNode::Lib(atom) => {
            variables_of(&atom.arguments).any(|held| held == variable) && mode_holds(algebra_relation(registry, &atom.relation), &atom.arguments, clause, placed)
        }
        IrNode::Comparison(comparison) if comparison.op == ConstraintOp::Eq => match comparison.second {
            Operand::Zero => comparison.first == variable,
            Operand::Variable(second) => (comparison.first == variable && placed[index(&second)]) || (second == variable && placed[index(&comparison.first)]),
        },
        _ => false,
    };
    let mut placed = vec![false; clause.variables.len()];
    bound.iter().for_each(|variable| placed[index(variable)] = true);
    let mut left = order;
    let mut sourced = Vec::with_capacity(left.len());
    while !left.is_empty() {
        let next = left.iter().position(|variable| always[index(variable)] || nodes.iter().any(|node| gives(node, *variable, &placed))).unwrap_or(0);
        let variable = left.remove(next);
        placed[index(&variable)] = true;
        sourced.push(variable);
    }
    sourced
}

/// Whether `variable` has a binding or a native finite orientation domain.
/// Availability does not turn a finite-domain variable into a physical binding.
fn bound_or_finite(clause: &ClauseIr, variable: Variable, bound: &[bool]) -> bool {
    bound[usize::from(variable.0)] || orientation_domain(&clause.variables[usize::from(variable.0)].ty).is_some()
}

/// Whether `union` can give its exports at `placed`, the placed variables of
/// its clause: each column of a branch that the union does not export is
/// placed or has a finite orientation domain, and each branch, with its columns among the placed variables
/// bound, grounds every variable it holds. A branch grounds a variable that
/// an atom of it binds, that an algebra relation outputs once a mode holds,
/// that an `=` binds from a grounded one, that a union of the branch binds
/// where that union grounds at the variables grounded so far, and a variable
/// of an orientation type, whose values are finite.
fn grounds(union: &Union, placed: &[bool]) -> bool {
    let reads_placed = |branch: &ClauseIr| branch.columns.iter().all(|column| union.exported.contains(column) || bound_or_finite(branch, *column, placed));
    union.branches.iter().all(reads_placed) && grounds_leaving(union, placed)
}

/// Whether `union` can give its exports at `placed` from its branches with
/// the nodes that [`kept_nodes`] leaves out: each branch, with its columns
/// among the placed variables bound, grounds every export of the union and
/// every variable that a kept node holds, as [`grounds`] gives. It holds
/// wherever `grounds` does, since a branch that has each column placed or
/// grounded leaves out no node. Where a branch reads a column that is neither
/// placed nor grounded, the union's check, at the rank of the last of its
/// columns, holds a binding of the exports to the whole branch.
fn grounds_leaving(union: &Union, placed: &[bool]) -> bool {
    union.branches.iter().all(|branch| {
        let grounding = Grounding::new(branch, placed);
        let kept = grounding.kept_nodes();
        union.exported.iter().copied().chain(kept.iter().flat_map(|&node| node_variables(&branch.nodes[node]))).all(|v| grounding.covers(v))
    })
}

/// The nodes of `branch`, a branch of a union, that a join of it keeps at
/// `bound`, the variables bound before the join: each node that holds no
/// column which is neither bound, nor grounded by the branch, nor of an
/// orientation type, as [`grounds_leaving`] gives.
pub(super) fn kept_nodes(branch: &ClauseIr, bound: &[Variable]) -> Vec<usize> {
    let mut placed = vec![false; branch.variables.len()];
    for variable in bound {
        placed[usize::from(variable.0)] = true;
    }
    Grounding::new(branch, &placed).kept_nodes()
}

/// The variables a branch grounds, with its columns among the placed
/// variables bound: the atoms of the branch, then the closure over the lib
/// modes, `=` and the inner unions that ground at the variables grounded so
/// far.
struct Grounding<'b> {
    branch: &'b ClauseIr,
    grounded: Vec<bool>,
}

impl<'b> Grounding<'b> {
    fn new(branch: &'b ClauseIr, placed: &[bool]) -> Self {
        let mut grounded = vec![false; branch.variables.len()];
        for column in branch.columns.iter() {
            grounded[usize::from(column.0)] = placed[usize::from(column.0)];
        }
        for variable in branch.nodes.iter().filter(|node| matches!(node, IrNode::Atom(_))).flat_map(bound_variables) {
            grounded[usize::from(variable.0)] = true;
        }
        loop {
            follow(branch, &mut grounded, &mut Vec::new());
            let ready: Vec<&Union> = branch
                .nodes
                .iter()
                .filter_map(|node| if let IrNode::Or(inner) = node { Some(inner) } else { None })
                .filter(|inner| grounds(inner, &grounded))
                .collect();
            let mut changed = false;
            for &export in ready.iter().flat_map(|inner| inner.exported.iter()) {
                changed |= !std::mem::replace(&mut grounded[usize::from(export.0)], true);
            }
            if !changed {
                break;
            }
        }
        Grounding { branch, grounded }
    }

    /// Whether `variable` is grounded or of an orientation type.
    fn covers(&self, variable: Variable) -> bool {
        bound_or_finite(self.branch, variable, &self.grounded)
    }

    /// The nodes that hold no column the branch does not cover.
    fn kept_nodes(&self) -> Vec<usize> {
        let kept = |node: &IrNode| node_variables(node).iter().all(|v| self.covers(*v) || !self.branch.columns.contains(v));
        (0..self.branch.nodes.len()).filter(|&node| kept(&self.branch.nodes[node])).collect()
    }
}

/// A variable the order places by a choice of its own, with its estimate.
struct Choice<'c> {
    variable: Variable,
    /// The estimated count of the variable's values.
    estimate: u64,
    /// For a variable that a union exports and no atom binds, that union,
    /// which must [`grounds`] before the choice; `None` for a variable that an
    /// atom binds.
    union: Option<&'c Union>,
}

impl Choice<'_> {
    /// Whether the choice can come next: its variable is outside `closure`
    /// and its union, if any, grounds at `closure`.
    fn is_next(&self, closure: &[bool]) -> bool {
        !closure[usize::from(self.variable.0)] && self.union.is_none_or(|union| grounds(union, closure))
    }
}

/// The choices of `clause` in the order of estimate then variable: each
/// variable that an atom binds, estimated at the rows of the smallest atom
/// that binds it, and each variable that a union exports and no atom or
/// comparison binds, estimated by [`union_estimate`], that the closure of the
/// choices before it has not placed, and whose union [`grounds`] at that
/// closure. `placed` holds the variables placed before any choice,
/// and `extend` adds a variable and its closure to a set of placed variables.
fn choices<'c>(
    clause: &'c ClauseIr,
    sizes: &RelationSizes,
    placed: &[bool],
    extend: &mut impl FnMut(&mut Vec<bool>, Variable),
) -> Vec<Choice<'c>> {
    let atoms = atom_rows(clause, sizes);
    let mut choices: Vec<Choice> = (0..clause.variables.len())
        .filter_map(|v| Some(Choice { variable: Variable(v as u16), estimate: atoms[v]?, union: None }))
        .collect();
    let mut closure = placed.to_vec();
    for choice in &choices {
        extend(&mut closure, choice.variable);
    }
    let unions = union_binders(clause);
    loop {
        let before = choices.len();
        for v in 0..clause.variables.len() {
            let (false, Some((_, union))) = (closure[v], unions[v]) else { continue };
            let variable = Variable(v as u16);
            if let Some(estimate) = union_estimate(clause, sizes, variable).filter(|_| grounds(union, &closure)) {
                extend(&mut closure, variable);
                choices.push(Choice { variable, estimate, union: Some(union) });
            }
        }
        if choices.len() == before {
            break;
        }
    }
    choices.sort_by_key(|choice| (choice.estimate, choice.variable.0));
    choices
}

/// The sequence of `choices` to place, each followed by its closure, of least
/// cost, where the cost of a sequence is the sum over its choices of the
/// product of the estimates of the choices up to and including that one, each
/// estimate by [`Estimates::at`] at the closure of the choices before it. A
/// choice is a variable outside the closure of the earlier choices, whose
/// union, if any, grounds at that closure, and the sequence ends when that closure
/// holds every choice. `choices` is in the order of estimate then index, and a
/// tie in cost goes to the sequence that is least in that order, so the order
/// of that sort is the order where costs are equal. `extend` adds a variable
/// and its closure to a set of placed variables, and `placed` holds the
/// variables placed before any choice.
///
/// The closure of a set of choices does not depend on their order, so the
/// search keeps, for each subset of the choices, the sequence of least cost
/// that reaches it, with the product of its estimates.
fn cheapest_sequence(choices: &[Choice<'_>], estimates: &Estimates, placed: &[bool], extend: &mut impl FnMut(&mut Vec<bool>, Variable)) -> Vec<Variable> {
    let count = choices.len();
    let mut closures: Vec<Vec<bool>> = Vec::with_capacity(1 << count);
    // The best (cost, choices as indexes into `choices`, product of the
    // estimates) to reach each subset.
    let mut best: Vec<Option<(u128, Vec<usize>, u128)>> = vec![None; 1 << count];
    let mut finish: Option<(u128, Vec<usize>, u128)> = None;
    for mask in 0..1usize << count {
        if mask == 0 {
            closures.push(placed.to_vec());
            best[0] = Some((0, Vec::new(), 1));
        } else {
            let low = mask.trailing_zeros() as usize;
            let mut closure = closures[mask & (mask - 1)].clone();
            extend(&mut closure, choices[low].variable);
            closures.push(closure);
            let mut found: Option<(u128, Vec<usize>, u128)> = None;
            for choice in (0..count).filter(|c| mask >> c & 1 == 1) {
                let before = mask & !(1 << choice);
                let Some((cost, earlier, product)) = &best[before] else { continue };
                let closure = &closures[before];
                if !choices[choice].is_next(closure) {
                    continue;
                }
                let mut next = earlier.clone();
                next.push(choice);
                let product = product.saturating_mul(u128::from(estimates.at(&choices[choice], closure)));
                let candidate = (cost.saturating_add(product), next, product);
                if found.as_ref().is_none_or(|found| (candidate.0, &candidate.1) < (found.0, &found.1)) {
                    found = Some(candidate);
                }
            }
            best[mask] = found;
        }
        if let Some(candidate) = &best[mask] {
            if choices.iter().all(|c| closures[mask][usize::from(c.variable.0)])
                && finish.as_ref().is_none_or(|finish| (candidate.0, &candidate.1) < (finish.0, &finish.1))
            {
                finish = Some(candidate.clone());
            }
        }
    }
    let (_, sequence, _) = finish.expect("the choices in order reach a set whose closure holds them all");
    sequence.into_iter().map(|c| choices[c].variable).collect()
}

/// The sequence of `choices` to place, each followed by its closure, where
/// the count of choices is outside the range that [`cheapest_sequence`]
/// searches, 0 or 1 or past [`SUBSET_BOUND`]: the choice of least estimate by
/// [`Estimates::at`] at the closure of the earlier ones, among those that
/// closure does not hold and whose union, if any, grounds at it, until none is
/// left. A tie goes to the first in the order of `choices`, of estimate then
/// index.
/// `extend` and `placed` are as for [`cheapest_sequence`].
fn sequence_in_order(choices: &[Choice<'_>], estimates: &Estimates, placed: &[bool], extend: &mut impl FnMut(&mut Vec<bool>, Variable)) -> Vec<Variable> {
    let mut closure = placed.to_vec();
    let mut sequence = Vec::new();
    while let Some(choice) = choices.iter().filter(|choice| choice.is_next(&closure)).min_by_key(|choice| estimates.at(choice, &closure)) {
        extend(&mut closure, choice.variable);
        sequence.push(choice.variable);
    }
    sequence
}

/// The atoms of a clause with their row counts, and the domain of each
/// variable, for the estimate of a choice at the variables placed before it.
struct Estimates {
    /// Each atom of known size: its row count and its variables.
    atoms: Vec<(u64, Vec<Variable>)>,
    /// The domain of each variable, by the variable's index: the row count of
    /// the smallest atom that binds it, or the size of its orientation type
    /// where that is less; 1 where neither is known.
    domains: Vec<u64>,
}

impl Estimates {
    fn new(clause: &ClauseIr, sizes: &RelationSizes) -> Self {
        let atoms: Vec<(u64, Vec<Variable>)> = clause
            .nodes
            .iter()
            .zip(sizes.0.iter())
            .filter_map(|(node, size)| match (node, size) {
                (IrNode::Atom(atom), NodeSize::Rows(count)) => Some((*count, variables_of(&atom.arguments).collect())),
                _ => None,
            })
            .collect();
        let registry = Registry::get();
        let domains = atom_rows(clause, sizes)
            .into_iter()
            .zip(clause.variables.iter())
            .map(|(rows, variable)| {
                let finite = domain(registry, &variable.ty).map(|values| values.len() as u64);
                match (rows, finite) {
                    (Some(rows), Some(finite)) => rows.min(finite),
                    (rows, finite) => rows.or(finite).unwrap_or(1),
                }
                .max(1)
            })
            .collect();
        Estimates { atoms, domains }
    }

    /// The estimate of `choice` at `closure`, the variables placed before it.
    /// For a variable that an atom binds, it is the least, over the atoms that
    /// bind it, of the atom's row count divided by the domains of the atom's
    /// other variables that `closure` holds, and at least 1. For an export of
    /// a union, it is the choice's own estimate.
    fn at(&self, choice: &Choice<'_>, closure: &[bool]) -> u64 {
        if choice.union.is_some() {
            return choice.estimate;
        }
        let variable = choice.variable;
        self.atoms
            .iter()
            .filter(|(_, variables)| variables.contains(&variable))
            .map(|(rows, variables)| {
                let mut placed: Vec<Variable> = variables.iter().copied().filter(|v| *v != variable && closure[usize::from(v.0)]).collect();
                placed.sort_by_key(|v| v.0);
                placed.dedup();
                let divisor = placed.iter().fold(1u64, |product, v| product.saturating_mul(self.domains[usize::from(v.0)]));
                (rows / divisor).max(1)
            })
            .min()
            .unwrap_or(choice.estimate)
    }
}

/// The count of rows of the smallest atom of `clause` that binds each
/// variable, by the variable's index, `None` for a variable that no atom of
/// known size binds.
fn atom_rows(clause: &ClauseIr, sizes: &RelationSizes) -> Vec<Option<u64>> {
    let mut rows: Vec<Option<u64>> = vec![None; clause.variables.len()];
    for (node, size) in clause.nodes.iter().zip(sizes.0.iter()) {
        if let (IrNode::Atom(atom), NodeSize::Rows(count)) = (node, size) {
            for variable in variables_of(&atom.arguments) {
                let held = &mut rows[usize::from(variable.0)];
                *held = Some(held.map_or(*count, |held| held.min(*count)));
            }
        }
    }
    rows
}

/// The union node of `clause` that binds each variable that no atom or
/// comparison binds, by the variable's index: the first union that exports
/// it, since the join takes its values from that union.
fn union_binders(clause: &ClauseIr) -> Vec<Option<(usize, &Union)>> {
    let mut binders: Vec<Option<(usize, &Union)>> = vec![None; clause.variables.len()];
    for (node, union) in clause.nodes.iter().enumerate().filter_map(|(node, n)| if let IrNode::Or(union) = n { Some((node, union)) } else { None }) {
        for variable in union.exported.iter() {
            binders[usize::from(variable.0)].get_or_insert((node, union));
        }
    }
    for node in clause.nodes.iter() {
        if let IrNode::Atom(_) | IrNode::Comparison(_) = node {
            for variable in bound_variables(node) {
                binders[usize::from(variable.0)] = None;
            }
        }
    }
    binders
}

/// The estimate of the count of values that the union which binds `variable`
/// in `clause` gives it: the sum over the union's branches of the rows of
/// the smallest atom of the branch that binds it, or, where a union of the
/// branch binds it, that union's estimate. `None` where `variable` has no
/// such union or a branch has no estimate.
fn union_estimate(clause: &ClauseIr, sizes: &RelationSizes, variable: Variable) -> Option<u64> {
    let (node, union) = union_binders(clause)[usize::from(variable.0)]?;
    let NodeSize::Clauses(branch_sizes) = &sizes.0[node] else { return None };
    union.branches.iter().zip(branch_sizes.iter()).try_fold(0u64, |total, (branch, sizes)| {
        let rows = atom_rows(branch, sizes)[usize::from(variable.0)].or_else(|| union_estimate(branch, sizes, variable))?;
        Some(total.saturating_add(rows))
    })
}

/// Whether an atom or a comparison of `clause` binds each variable, by the
/// variable's index: such a variable waits on nothing before the order places
/// it. A variable that only unions bind waits until its union [`grounds`], and
/// a variable that only an algebra relation binds until a mode of that
/// relation holds.
fn direct_variables(clause: &ClauseIr) -> Vec<bool> {
    let mut direct = vec![false; clause.variables.len()];
    for node in clause.nodes.iter() {
        if let IrNode::Atom(_) | IrNode::Comparison(_) = node {
            for variable in bound_variables(node) {
                direct[usize::from(variable.0)] = true;
            }
        }
    }
    direct
}

/// The variables that `node` binds in its enclosing clause: an atom's, a
/// comparison's, and the variables a union exports.
pub(super) fn bound_variables(node: &IrNode) -> Vec<Variable> {
    match node {
        IrNode::Atom(atom) => variables_of(&atom.arguments).collect(),
        IrNode::Lib(atom) => variables_of(&atom.arguments).collect(),
        IrNode::Comparison(comparison) => {
            let second = match comparison.second {
                Operand::Variable(second) => Some(second),
                Operand::Zero => None,
            };
            std::iter::once(comparison.first).chain(second).collect()
        }
        IrNode::Or(union) => union.exported.to_vec(),
        IrNode::Not(_) | IrNode::Counterexample(_) => Vec::new(),
    }
}

/// Each variable that stands at a column of `arguments`.
pub(super) fn variables_of(arguments: &Arguments) -> impl Iterator<Item = Variable> + '_ {
    arguments.0.iter().filter_map(|(_, argument)| match argument {
        Argument::Variable(variable) => Some(*variable),
        Argument::Term(_) => None,
    })
}

/// The declaration of the algebra relation or relation macro `name`.
pub(super) fn algebra_relation<'r>(registry: &'r Registry, name: &LibName) -> &'r AlgebraRelation {
    registry.algebra_relation(name).expect("a lib atom of a checked clause reads an algebra relation or a relation macro")
}

/// Whether the columns of `arguments` whose variables `bound` holds, or
/// whose argument is a term, satisfy a mode of `relation`, or `relation`
/// has none. A variable of an orientation type is bound by its finite
/// domain.
pub(super) fn mode_holds(relation: &AlgebraRelation, arguments: &Arguments, clause: &ClauseIr, bound: &[bool]) -> bool {
    if relation.modes.is_empty() {
        return true;
    }
    let mut columns = vec![false; relation.columns.len()];
    for (column, argument) in arguments.0.iter() {
        columns[usize::from(column.0)] = match argument {
            Argument::Term(_) => true,
            Argument::Variable(variable) => bound_or_finite(clause, *variable, bound),
        };
    }
    crate::algebra::satisfied_mode(relation, &columns).is_some()
}

