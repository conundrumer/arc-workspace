//! The check of the names that reach past a form: the reads of the parts of
//! a `RIGID_DET` form (`docs/arclog/rigid.md#semantics`), and the names of
//! the proposers a clause gives.

use super::types::result;
use super::{each_node, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{OutputName, OutputOwner, RelationRef, RigidDetName};
use crate::resolver::form_columns::rigid_outputs;
use crate::resolver::ResolvedProgram;

/// [`CheckId::RigidPartsAndProposers`].
pub struct RigidPartsAndProposersCheck;

impl Check for RigidPartsAndProposersCheck {
    fn id(&self) -> CheckId {
        CheckId::RigidPartsAndProposers
    }

    /// No key, since the check reads the `RIGID_DET` forms of the case
    /// program.
    fn cache_key(&self, _: &KeyInput<'_>) -> Option<CheckCacheKey> {
        None
    }

    /// Refuses, at the clause, a proposer whose name is not an uppercase
    /// letter and then letters and digits, and, at the atom, a read of an
    /// output of a `RIGID_DET` form of the case program that gives no such
    /// output: a part that no atom of the form reads. A read of a form that
    /// the case program does not hold is the resolver's: the case is
    /// undefined where it reads it.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let program = input.scope.program;
        let mut refused: Vec<(NodePath, &str)> = Vec::new();
        each_node(NodeRef::from(input.form), &NodePath::default(), &mut |node, at| match (node, node.atom().map(|atom| &atom.relation)) {
            (NodeRef::Clause(clause), _) if !clause.proposers.iter().all(|proposer| is_proposer_name(&proposer.0)) => {
                refused.push((at.clone(), "a proposer's name is an uppercase letter, then letters and digits"));
            }
            (_, Some(RelationRef::Output(output @ OutputName { of: OutputOwner::RigidDet(owner), .. }))) if !gives(program, owner, output) => {
                refused.push((at.clone(), "no part of the `RIGID_DET` form gives the output"));
            }
            _ => {}
        });
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        result(refused.into_iter().map(|(at, message)| Refusal { message: message.into(), at: order.canonical_path(&at) }).collect())
    }

    /// A clause's proposers stand before its body, and a read names a form
    /// written before it, so no completion undoes a refusal: each stands
    /// once its node is written.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::standing(prefix, self.check(&super::prefix::whole(prefix)), &|_| true)
    }
}

/// Whether `name` is a proposer's name: an uppercase letter, then letters
/// and digits.
fn is_proposer_name(name: &str) -> bool {
    let mut chars = name.chars();
    chars.next().is_some_and(|c| c.is_ascii_uppercase()) && chars.all(|c| c.is_ascii_alphanumeric())
}

/// Whether each `RIGID_DET` form named `owner` that `program` holds gives
/// `output`, which holds where the program holds none.
fn gives(program: &ResolvedProgram, owner: &RigidDetName, output: &OutputName) -> bool {
    let mut forms = Vec::new();
    each_node(NodeRef::Program(program.program.value()), &NodePath::default(), &mut |node, _| {
        if let NodeRef::RigidDet(form) = node {
            if form.name == *owner {
                forms.push(form);
            }
        }
    });
    forms.iter().all(|form| rigid_outputs(form).iter().any(|(steps, _)| **steps == *output.path))
}
