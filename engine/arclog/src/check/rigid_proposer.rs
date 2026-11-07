//! The check of the names that reach past a form: the reads of the parts of
//! a `RIGID_DET` form (`docs/arclog/rigid.md#semantics`), and the names of
//! the proposers a clause gives, and the rules that a clause that names a
//! proposer has no body and names one proposer.

use super::types::result;
use super::{each_node, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Clause, ClauseKeyword, OutputName, OutputOwner, Program, RelationRef, RigidDetName};
use crate::resolver::form_columns::rigid_outputs;
use crate::resolver::ResolvedProgram;
use crate::solver::Case;

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
    /// letter and then letters and digits, a `DET` or `RULE` that names
    /// a proposer and holds a body, and a `DET` or `RULE` that names more
    /// than one proposer (`docs/arclog/arclog.md#program`), and,
    /// at the atom, a read of an
    /// output of a `RIGID_DET` form of the case program that gives no such
    /// output: a part that no atom of the form reads. A read of a form that
    /// the case program does not hold is the resolver's: the case is
    /// undefined where it reads it.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let program = input.scope.program;
        let mut refused: Vec<(NodePath, &str)> = Vec::new();
        each_node(NodeRef::from(input.form), &NodePath::default(), &mut |node, at| {
            if let NodeRef::Clause(clause) = node {
                if !clause.proposers.iter().all(|proposer| is_proposer_name(&proposer.0)) {
                    refused.push((at.into(), "a proposer's name is an uppercase letter, then letters and digits"));
                }
                if names_proposer_and_holds_body(clause) {
                    refused.push((at.into(), "a `DET` or `RULE` that names a proposer has no body"));
                }
                if names_several_proposers(clause) {
                    refused.push((at.into(), "a `DET` or `RULE` names at most one proposer"));
                }
            }
            if let Some(RelationRef::Output(output @ OutputName { of: OutputOwner::RigidDet(owner), .. })) = node.atom().map(|atom| &atom.relation) {
                if !gives(program, owner, output) {
                    refused.push((at.into(), "no part of the `RIGID_DET` form gives the output"));
                }
            }
        });
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        result(refused.into_iter().map(|(at, message)| Refusal { message: message.into(), at: input.refusal_path(&at) }).collect())
    }

    /// A clause's proposers stand before its body, and a read names a form
    /// written before it, so no completion undoes a refusal: each stands
    /// once its node is written.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::standing(prefix, self.check(&super::prefix::whole(prefix)), &|_| true)
    }
}

/// Whether `clause` is a `DET` or `RULE` that names a proposer and holds a
/// conjunct in its body.
fn names_proposer_and_holds_body(clause: &Clause) -> bool {
    matches!(clause.keyword, ClauseKeyword::Det | ClauseKeyword::Rule) && !clause.proposers.is_empty() && !clause.body.value().conjuncts.is_empty()
}

/// Whether `clause` is a `DET` or `RULE` that names more than one proposer.
/// A `DET_OR_RULE` or `RULE_OR_DET` line may name several, and each of its
/// readings names one.
fn names_several_proposers(clause: &Clause) -> bool {
    matches!(clause.keyword, ClauseKeyword::Det | ClauseKeyword::Rule) && clause.proposers.len() > 1
}

/// The refusal of a case program read from a solver's files whose reading of
/// a line gives no program, which `case` gives ([`Case::reading_fault`]), at
/// the last form of the program.
pub(super) fn reading_fault(case: &Case, program: &Program) -> Option<Refusal> {
    let message = case.reading_fault()?;
    let at = program.forms.len().checked_sub(1).map_or_else(NodePath::default, |last| NodePath::top(last as u32));
    Some(Refusal { message: message.into(), at })
}

/// Whether `name` is a proposer's name: an uppercase letter, then letters
/// and digits.
pub(crate) fn is_proposer_name(name: &str) -> bool {
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
