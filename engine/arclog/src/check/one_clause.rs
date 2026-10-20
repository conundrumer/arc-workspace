//! The check of one clause per relation in a block.

use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::path::NodePath;
use crate::program::{Clause, ClauseKeyword, Form};

/// [`CheckId::OneClause`].
pub struct OneClauseCheck;

impl Check for OneClauseCheck {
    fn id(&self) -> CheckId {
        CheckId::OneClause
    }

    /// No key, since the check reads the forms before the form under check.
    fn cache_key(&self, _: &KeyInput<'_>) -> Option<CheckCacheKey> {
        None
    }

    /// Refuses a top-level clause of a relation that an earlier top-level
    /// clause of the case program in the same block of its file derives,
    /// the blocks as [`super::CaseFiles`] gives them: a union is one clause
    /// whose body is an `OR` (`docs/arclog/arclog.md#disjunction`). A
    /// `DET_OR_RULE` or `RULE_OR_DET` line is no clause of a block here,
    /// since its reading in each case is the alt's. A program with no
    /// files, as a synthesized one, has no blocks, and passes: the prefix
    /// form refuses a second clause in a decode.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let Some(files) = input.scope.files else { return CheckResult::Pass };
        let forms = &input.scope.program.program.value().forms;
        let index = input.path.0.first().expect("a check reads a top-level form").0;
        let own = files.block(input.path);
        let before: Vec<Form> = (0..index).filter(|&earlier| files.block(&NodePath::top(earlier)) == own).map(|earlier| forms[earlier as usize].clone()).collect();
        if derived_before(input.form, &before) {
            CheckResult::Refuse(Box::new([refusal()]))
        } else {
            CheckResult::Pass
        }
    }

    /// Refuses the declaration of a relation that a complete form of the
    /// prefix already derives, since no clause written later undoes it.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        if derived_before(prefix.partial, prefix.complete) {
            PrefixResult::Refuse(Box::new([refusal()]))
        } else {
            PrefixResult::Undecided
        }
    }
}

fn refusal() -> Refusal {
    Refusal { message: "the relation has a clause earlier in the block: a union is one clause whose body is an `OR`".into(), at: NodePath::default() }
}

/// Whether `form` is a clause of a block whose relation a clause of
/// `before` derives.
fn derived_before(form: &Form, before: &[Form]) -> bool {
    let Some(clause) = block_clause(form) else { return false };
    before.iter().filter_map(block_clause).any(|earlier| earlier.derives == clause.derives)
}

/// The clause that `form` is, where it is a `RULE` or a `DET`.
fn block_clause(form: &Form) -> Option<&Clause> {
    match form {
        Form::Clause(clause) if matches!(clause.value().keyword, ClauseKeyword::Rule | ClauseKeyword::Det) => Some(clause.value()),
        _ => None,
    }
}
