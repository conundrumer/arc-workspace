//! The check of the picks: the `ONE` marks of a clause and the `CHOOSE`
//! forms (`docs/arclog/constraints.md#one`,
//! `docs/arclog/constraints.md#choose`).

use super::types::result;
use super::{each_node, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Atom, Body, Choose, ChoosePart, Clause, ColumnName, Conjunct, Form, ConstraintOp, LabelId, LabelUse, Operand, RelationRef, Site, SiteArg};

/// [`CheckId::Picks`].
pub struct PicksCheck;

impl Check for PicksCheck {
    fn id(&self) -> CheckId {
        CheckId::Picks
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
    }

    /// Refuses an atom that reads `ONE`, a mark that stands only after a
    /// clause's body. It refuses, at the clause, a `ONE` mark that names a
    /// label which is no column of the clause, as a mark with a key on a clause whose columns
    /// a proposer gives. At a `CHOOSE` form, it refuses:
    /// - a form with no `never` body, since a pick with no never is written
    ///   with `ONE` marks;
    /// - at a `never` body, a body that holds fewer than two positive atoms
    ///   of the relation of the first positive atom of the `from` clause;
    /// - a form whose every `never` body states only that one candidate
    ///   stands in two rows, which `ONE` marks state, as `states_one`
    ///   gives.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        refusals(input.form, true)
    }

    /// The check over the form once it ends: a mark follows the body of its
    /// clause, and the checks of a `CHOOSE` form are decided at its `END`
    /// (`docs/engine/synthesis.md#token-mask`). An atom that reads `ONE` is
    /// refused once it is written.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::settled_result(prefix, refusals(prefix.partial, prefix.open.is_none()))
    }
}

/// The refusals of [`PicksCheck`] on `form`, those of its `ONE` marks and
/// its `CHOOSE` forms only where `ended`, where the form is written whole.
fn refusals(form: &Form, ended: bool) -> CheckResult {
    let mut refused: Vec<(NodePath, &str)> = Vec::new();
    each_node(NodeRef::from(form), &NodePath::default(), &mut |node, at| match (node, node.atom()) {
        (NodeRef::Clause(clause), _) if ended && !marks_name_columns(clause) => refused.push((at.clone(), "a `ONE` mark names only columns of the clause")),
        (NodeRef::Choose(choose), _) if ended => choose_refusals(choose, at, &mut refused),
        (_, Some(Atom { relation: RelationRef::Lib(name), .. })) if *name.0 == *crate::read::spelling::ONE => {
            refused.push((at.clone(), "`ONE` stands at a clause's top level, after its body"));
        }
        _ => {}
    });
    if refused.is_empty() {
        return CheckResult::Pass;
    }
    let order = CanonicalOrder::of(form, &mut SearchBudget::new());
    result(refused.into_iter().map(|(at, message)| Refusal { message: message.into(), at: order.canonical_path(&at) }).collect())
}

/// Whether each label of each `ONE` mark of `clause` is a column of the
/// clause.
fn marks_name_columns(clause: &Clause) -> bool {
    let column = |label: &LabelId| clause.columns.iter().any(|column| column.label == *label);
    clause.ones.iter().all(|mark| mark.key.iter().all(column))
}

/// Pushes onto `out` each refusal of the `CHOOSE` form `choose`, at `at`.
fn choose_refusals(choose: &Choose, at: &NodePath, out: &mut Vec<(NodePath, &str)>) {
    if choose.never.is_empty() {
        out.push((at.clone(), "a `CHOOSE` form is written only for a pick with a `never`"));
    }
    if let Some(candidate) = positive_atoms(choose.from.value()).next() {
        for (index, never) in choose.never.iter().enumerate() {
            if positive_atoms(never.value()).filter(|atom| atom.relation == candidate.relation).count() < 2 {
                out.push((at.child(choose.position(ChoosePart::Never(index))), "a `never` reads the candidate relation twice"));
            }
        }
    }
    if states_one(choose) {
        out.push((at.clone(), "every `never` says that one candidate stands in two rows, so `ONE` marks state the pick"));
    }
}

/// The positive atoms at the top level of `body`.
fn positive_atoms(body: &Body) -> impl Iterator<Item = &Atom> {
    body.conjuncts.iter().filter_map(|conjunct| match conjunct {
        Conjunct::Atom(atom) => Some(atom.value()),
        _ => None,
    })
}

/// Whether `choose` is a pick that `ONE` marks state: its `from` clause is
/// one atom, the candidate, whose every site is a label, and each `never`
/// body is two atoms of the candidate's relation on the candidate's sites,
/// and one group of `!=` constraints, one constraint or an `OR` whose every
/// branch is one, over exactly the pairs of labels at which the two atoms
/// differ. A form with no `never` body is such a pick.
fn states_one(choose: &Choose) -> bool {
    let [Conjunct::Atom(candidate)] = &choose.from.value().conjuncts[..] else { return false };
    let candidate = candidate.value();
    let Some(sites) = site_labels(candidate) else { return false };
    let keys: Vec<&SiteKey<'_>> = sites.iter().map(|(key, _)| key).collect();
    choose.never.iter().all(|never| {
        let (atoms, rest): (Vec<&Conjunct>, Vec<&Conjunct>) = never.value().conjuncts.iter().partition(|conjunct| match conjunct {
            Conjunct::Atom(atom) => atom.value().relation == candidate.relation,
            _ => false,
        });
        let [Conjunct::Atom(first), Conjunct::Atom(second)] = atoms[..] else { return false };
        let (Some(first), Some(second)) = (site_labels(first.value()), site_labels(second.value())) else { return false };
        if !same_keys(&first, &keys) || !same_keys(&second, &keys) {
            return false;
        }
        let mut differ: Vec<(u32, u32)> = Vec::new();
        for (key, label) in &first {
            let other = second.iter().find(|(own, _)| own == key).map(|(_, label)| *label).expect("the two atoms have the same sites");
            if other != *label {
                differ.push(pair(*label, other));
            }
        }
        let [group] = &rest[..] else { return false };
        let Some(group) = inequalities(group) else { return false };
        same_set(&group, &differ)
    })
}

/// A site of an atom by its column, and by the field or the named label of
/// a column of a type parameter: `(:P *P)` by `P`, `(:key (:O *O))` and
/// `(:key O)` by `key` and `O`.
type SiteKey<'a> = (&'a ColumnName, Option<&'a ColumnName>);

/// The label of each site of `atom` by its [`SiteKey`], or none where a
/// site holds no label.
fn site_labels(atom: &Atom) -> Option<Vec<(SiteKey<'_>, LabelId)>> {
    let mut out = Vec::new();
    for site in atom.sites.iter() {
        for arg in site.value.args.iter() {
            let (field, label) = match arg {
                SiteArg::Label(label) => (None, *label),
                SiteArg::NamedLabel { name, label } => (Some(name), *label),
                SiteArg::Field(Site { column, value }) => match &value.args[..] {
                    [arg] => (Some(column), arg.label()?),
                    _ => return None,
                },
            };
            out.push(((&site.column, field), label_id(label)?));
        }
    }
    Some(out)
}

fn label_id(label: LabelUse) -> Option<LabelId> {
    match label {
        LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id) => Some(id),
        LabelUse::Zero => None,
    }
}

/// Whether the sites of `labels` are at exactly the keys `keys`.
fn same_keys(labels: &[(SiteKey<'_>, LabelId)], keys: &[&SiteKey<'_>]) -> bool {
    labels.iter().all(|(key, _)| keys.contains(&key)) && keys.iter().all(|key| labels.iter().any(|(own, _)| own == *key))
}

/// The two labels as an unordered pair.
fn pair(a: LabelId, b: LabelId) -> (u32, u32) {
    (a.0.min(b.0), a.0.max(b.0))
}

/// The pairs of labels of `conjunct` where it is one `!=` constraint over
/// two labels, or an `OR` whose every branch is one.
fn inequalities(conjunct: &Conjunct) -> Option<Vec<(u32, u32)>> {
    let inequality = |conjunct: &Conjunct| match conjunct {
        Conjunct::Constraint(constraint) if constraint.op == ConstraintOp::Ne => match constraint.second {
            Operand::Label(second) => Some(pair(constraint.first.label, second.label)),
            Operand::Zero => None,
        },
        _ => None,
    };
    match conjunct {
        Conjunct::Or(branches) => branches
            .iter()
            .map(|branch| match &branch.value().conjuncts[..] {
                [only] => inequality(only),
                _ => None,
            })
            .collect(),
        conjunct => inequality(conjunct).map(|pair| vec![pair]),
    }
}

fn same_set(a: &[(u32, u32)], b: &[(u32, u32)]) -> bool {
    a.iter().all(|x| b.contains(x)) && b.iter().all(|x| a.contains(x))
}
