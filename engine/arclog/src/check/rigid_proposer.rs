//! The check of the names that reach past a form: the reads of the parts of
//! a `RIGID_DET` form (`docs/arclog/rigid.md#semantics`), and the names of
//! the proposers a clause gives, and the rules that a clause that names a
//! proposer has no body and names one proposer.

use super::types::result;
use super::{each_node, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::canonical::{prediction, relation_of};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Clause, ClauseKeyword, OutputName, OutputOwner, OutputStep, Program, RelationRef, RigidDetName, RigidDetPart};
use crate::resolver::form_columns::{part_steps, rigid_outputs};
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
    /// than one proposer (`docs/arclog/arclog.md#program`), at the body of a
    /// `DET` that the file writes with no proposer and no conjunct, which gives no
    /// value, at the second of two parts of a `RIGID_DET` form whose outputs
    /// begin with one name (`docs/arclog/rigid.md#form`), at a `&prediction`
    /// clause of a `DEMONSTRATED` form that makes no label named as a column
    /// of the `value` head (`docs/arclog/arclog.md#demonstrated`), and,
    /// at the atom, a read of an
    /// output of a `RIGID_DET` form of the case program that gives no such
    /// output: a part that no atom of the form reads. A read of a form that
    /// the case program does not hold is the resolver's: the case is
    /// undefined where it reads it.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        self.refusals(input, true)
    }

    /// A clause's proposers stand before its body, and a read names a form
    /// written before it, so no completion undoes a refusal: each stands
    /// once its node is written.
    ///
    /// The refusal of a `DET` with no body stands once its body is complete:
    /// a body that is open may yet take a conjunct. That of a `&prediction`
    /// clause stands once the form is complete: the clause stands in the
    /// prefix with the columns filled so far. The refusal of a part that
    /// begins its output as an earlier part does is the grammar's alone: it
    /// reads the part's relation, where the checks of the candidates of an
    /// open atom share their results by the class of the relation.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        let unsettled = |at: &NodePath| match node_at(NodeRef::from(prefix.partial), at) {
            Some(NodeRef::Body(body)) => body.conjuncts.is_empty() && at.0.split_last().is_some_and(|(_, parent)| prefix.is_open(&NodePath(parent.into()))),
            Some(NodeRef::Clause(clause)) => relation_of(&clause.derives) == prediction() && prefix.open.is_some(),
            _ => false,
        };
        super::prefix::standing(prefix, self.refusals(&super::prefix::whole(prefix), false), &|at| !unsettled(at))
    }
}

impl RigidPartsAndProposersCheck {
    /// The refusals of [`Check::check`] of the form of `input`; with `parts`,
    /// those at a part of a `RIGID_DET` form whose output begins as an
    /// earlier part's does.
    fn refusals(&self, input: &CheckInput<'_>, parts: bool) -> CheckResult {
        let program = input.scope.program;
        // A case's reading of a line makes `DET` clauses that the file does not write.
        let written = input.scope.files.map_or(true, |files| files.writes(input.path));
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
                if written && holds_nothing(clause) {
                    refused.push((NodePath::from(at).child(0), "a `DET` holds a body or names a proposer, since a `DET` of no body and no proposer gives no value"));
                }
            }
            if let NodeRef::Demonstrated(form) = node {
                for clause in crate::eval::demonstrated::predictions_missing_a_value_column(form, &NodePath::from(at)) {
                    refused.push((clause, "a `&prediction` clause makes a label named as each column of the `value` head"));
                }
            }
            if let (true, NodeRef::RigidDet(form)) = (parts, node) {
                let mut begun: Vec<OutputStep> = Vec::new();
                for (part, index) in form.parts.iter().zip(0usize..) {
                    let Some(step) = part_steps(&part.value().relation).and_then(|steps| steps.into_iter().next()) else { continue };
                    if begun.contains(&step) {
                        let at = NodePath::from(at).child(form.position(RigidDetPart::Part(index)));
                        refused.push((at, "the output of a part of a `RIGID_DET` form begins with a step that the output of an earlier part begins with"));
                    }
                    begun.push(step);
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
}

/// Whether `clause` is a `DET` that names no proposer and holds no conjunct.
fn holds_nothing(clause: &Clause) -> bool {
    clause.keyword == ClauseKeyword::Det && clause.proposers.is_empty() && clause.body.value().conjuncts.is_empty()
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
