//! The pose rule's check.

use super::inference::{FormInference, Inference, SiteUse};
use super::types::{result, PoseOr};
use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::types::{Meet, ValueType};

/// [`CheckId::PoseRule`].
pub struct PoseRuleCheck;

impl Check for PoseRuleCheck {
    fn id(&self) -> CheckId {
        CheckId::PoseRule
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
    }

    /// Refuses each site of a Pose label of the form that
    /// `docs/arclog/rigid.md#the-pose` does not give: a site whose column
    /// gives a type other than the label's, or that gives no type and is no
    /// column of a relation that clauses, a `CHOOSE` form or a
    /// `DEMONSTRATED` form derive, a parameter included, of an instance's
    /// input, of an instance whose inputs read its outputs, or of a lib
    /// relation that takes a Pose type; and a lib atom whose columns of one
    /// shared Pose type hold labels of two Pose types; and a site of a label
    /// that is no Pose at a column of `(pose-or <type>)`, where the label's
    /// type and that type have an empty meet. The rule on `<`,
    /// `<=`, `>` and `>=` is the type check's.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let inference = input.scope.inference;
        let Some(form) = inference.infer(input.path) else { return CheckResult::Pass };
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        let reading = form.reading(PoseOr::Open);
        let mut refusals = Vec::new();
        let mut shared: Vec<(*const crate::program::Atom, &crate::program::path::NodePath, ValueType)> = Vec::new();
        for site in &form.walk.uses {
            let Some(atom) = site.atom else { continue };
            let Some(pose) = form.pose_of(site.label) else {
                if let Some(message) = pose_or_conflict(inference, &form, site, atom) {
                    refusals.push(Refusal { message: message.into(), at: order.canonical_path(&site.at) });
                }
                continue;
            };
            let admitted = match inference.site_type(reading, atom, &site.column) {
                Some(ty) => ty == *pose,
                None => inference.admits_pose(reading, atom, &site.column),
            };
            if !admitted {
                let message = "a Pose label stands at a site that `docs/arclog/rigid.md#the-pose` does not give";
                refusals.push(Refusal { message: message.into(), at: order.canonical_path(&site.at) });
                continue;
            }
            if inference.shares_pose(reading, atom, &site.column) {
                let atom = atom as *const crate::program::Atom;
                if shared.iter().any(|(found, _, ty)| *found == atom && ty != pose) {
                    let message = "the atom's columns of one Pose type hold labels of two Pose types";
                    refusals.push(Refusal { message: message.into(), at: order.canonical_path(&site.at) });
                }
                shared.push((atom, &site.at, pose.clone()));
            }
        }
        result(refusals)
    }

    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::settled(prefix, self)
    }
}

/// Why the site of a label that is no Pose, at a column of
/// `(pose-or <type>)`, is refused: its label's type and the column's have
/// an empty meet.
fn pose_or_conflict<'a>(inference: &Inference<'a>, form: &FormInference<'a>, site: &SiteUse<'_>, atom: &crate::program::Atom) -> Option<&'static str> {
    let label = form.label(site.label)?;
    let column = inference.site_type(form.reading(PoseOr::Given), atom, &site.column)?;
    if inference.site_type(form.reading(PoseOr::Open), atom, &site.column).is_some() {
        return None;
    }
    matches!(label.meet(&column), Meet::Empty).then_some("a label of a type that meets no type of the `pose-or` column stands at the column")
}
