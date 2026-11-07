//! The digest of IR under a renaming of its variables that keeps the order of
//! their indices.
//!
//! A variable of a clause is the canonical position of its label in the
//! whole scope of the form ([`crate::eval::ir::IrBuilder::variable`]), so
//! the variables of a body part have the indices that the rest of the scope
//! gives them. A search of the part reads its variables by their relative
//! order of indices alone, where an index breaks a tie, and reads the
//! other variables of the scope not at all. [`Names`] gives each variable
//! that some node of a part mentions, nested nodes included, the rank of its
//! index among them, so the digest of two parts that differ only by the
//! indices of the scope's other variables is equal.

use std::hash::{Hash, Hasher};

use crate::eval::ir::{Argument, Arguments, ClauseIr, IrNode, Operand, Variable};
use crate::hash::StableHasher;

/// The rank of each variable that some node mentions, among the variables
/// the nodes mention.
pub(super) struct Names {
    ranks: Vec<u16>,
    /// The variables mentioned, in the order of their indices.
    mentioned: Vec<Variable>,
}

impl Names {
    /// The ranks of the variables that `nodes` and `also` mention, among the
    /// variables of `clause`.
    pub(super) fn of<'a>(clause: &ClauseIr, nodes: impl IntoIterator<Item = &'a IrNode>, also: &[Variable]) -> Names {
        let mut found: Vec<Variable> = also.to_vec();
        for node in nodes {
            mention(node, &mut found);
        }
        found.sort_unstable_by_key(|variable| variable.0);
        found.dedup();
        let mut ranks = vec![u16::MAX; clause.variables.len()];
        for (rank, variable) in found.iter().enumerate() {
            ranks[usize::from(variable.0)] = u16::try_from(rank).expect("fewer than 2^16 variables");
        }
        Names { ranks, mentioned: found }
    }

    fn rank(&self, variable: Variable) -> u16 {
        let rank = self.ranks[usize::from(variable.0)];
        debug_assert_ne!(rank, u16::MAX, "a variable that no node mentions");
        rank
    }

    /// Writes the rank of each of `variables`.
    pub(super) fn variables(&self, variables: &[Variable], into: &mut StableHasher) {
        variables.len().hash(into);
        for &variable in variables {
            self.rank(variable).hash(into);
        }
    }

    /// Writes the rank and the type of each variable mentioned, in rank
    /// order.
    pub(super) fn types(&self, clause: &ClauseIr, into: &mut StableHasher) {
        self.mentioned.len().hash(into);
        for variable in &self.mentioned {
            clause.variables[usize::from(variable.0)].ty.hash(into);
        }
    }

    /// Writes `node`, with each variable by its rank and with no source of
    /// its relation, which a search reads in the rows of its inputs alone.
    pub(super) fn node(&self, node: &IrNode, into: &mut StableHasher) {
        match node {
            IrNode::Atom(atom) => {
                0u8.hash(into);
                self.arguments(&atom.arguments, into);
            }
            IrNode::Lib(atom) => {
                1u8.hash(into);
                atom.relation.hash(into);
                self.arguments(&atom.arguments, into);
            }
            IrNode::Comparison(comparison) => {
                2u8.hash(into);
                comparison.op.hash(into);
                self.rank(comparison.first).hash(into);
                match comparison.second {
                    Operand::Variable(second) => (1u8, self.rank(second)).hash(into),
                    Operand::Zero => (0u8, 0u16).hash(into),
                }
                comparison.binds_first.hash(into);
            }
            IrNode::Not(filter) => {
                3u8.hash(into);
                self.variables(&filter.outer, into);
                self.clause(&filter.body, into);
            }
            IrNode::Counterexample(filter) => {
                4u8.hash(into);
                self.variables(&filter.outer, into);
                self.clause(&filter.body, into);
            }
            IrNode::Or(union) => {
                5u8.hash(into);
                self.variables(&union.exported, into);
                union.branches.len().hash(into);
                for branch in &union.branches {
                    self.clause(branch, into);
                }
            }
        }
    }

    /// Writes the nodes and the columns of `clause`, a clause nested in the
    /// nodes.
    pub(super) fn clause(&self, clause: &ClauseIr, into: &mut StableHasher) {
        clause.nodes.len().hash(into);
        for node in &clause.nodes {
            self.node(node, into);
        }
        self.variables(&clause.columns, into);
    }

    fn arguments(&self, arguments: &Arguments, into: &mut StableHasher) {
        arguments.0.len().hash(into);
        for (column, argument) in arguments.0.iter() {
            column.hash(into);
            match argument {
                Argument::Variable(variable) => (1u8, self.rank(*variable)).hash(into),
                Argument::Term(term) => (0u8, term).hash(into),
            }
        }
    }
}

/// Adds to `found` each variable that `node` mentions, nested nodes included.
fn mention(node: &IrNode, found: &mut Vec<Variable>) {
    let arguments = |arguments: &Arguments, found: &mut Vec<Variable>| {
        found.extend(arguments.0.iter().filter_map(|(_, argument)| match argument {
            Argument::Variable(variable) => Some(*variable),
            Argument::Term(_) => None,
        }));
    };
    let nested = |clause: &ClauseIr, found: &mut Vec<Variable>| {
        for node in &clause.nodes {
            mention(node, found);
        }
        found.extend(clause.columns.iter().copied());
    };
    match node {
        IrNode::Atom(atom) => arguments(&atom.arguments, found),
        IrNode::Lib(atom) => arguments(&atom.arguments, found),
        IrNode::Comparison(comparison) => {
            found.push(comparison.first);
            if let Operand::Variable(second) = comparison.second {
                found.push(second);
            }
        }
        IrNode::Not(filter) | IrNode::Counterexample(filter) => {
            found.extend(filter.outer.iter().copied());
            nested(&filter.body, found);
        }
        IrNode::Or(union) => {
            found.extend(union.exported.iter().copied());
            for branch in &union.branches {
                nested(branch, found);
            }
        }
    }
}

/// A digest of what `write` writes.
pub(super) fn digest(write: impl FnOnce(&mut StableHasher)) -> u64 {
    let mut hasher = StableHasher::new();
    write(&mut hasher);
    hasher.finish()
}
