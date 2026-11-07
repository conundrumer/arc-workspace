//! The check of the picks: the `ONE` marks of a clause and the `CHOOSE`
//! forms (`docs/arclog/constraints.md#one`,
//! `docs/arclog/constraints.md#choose`).

use super::types::result;
use super::{each_node, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::path::{node_at, NodePath, NodeRef, PathStep};
use crate::registry::{LibName, Registry};
use crate::resolver::registry_columns::{is_domain, proposer_columns};
use crate::program::{Atom, Body, Choose, ChoosePart, Clause, ClauseKeyword, ColumnName, Conjunct, ConstraintOp, LabelId, LabelUse, Operand, RelationRef, Site, SiteArg};

/// [`CheckId::Picks`].
pub struct PicksCheck;

impl Check for PicksCheck {
    fn id(&self) -> CheckId {
        CheckId::Picks
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
    }

    /// Refuses a `SET` mark on a clause that is a `RULE`, has a body, or
    /// names a proposer other than one of one column that the registry does
    /// not mark `domain`. Refuses an atom that reads `ONE`, a mark that stands only after a
    /// clause's body. It refuses, at the clause, a `ONE` mark that names a
    /// label which is no column of the clause, as a mark with a key on a clause whose columns
    /// a proposer gives. At a `CHOOSE` form, it refuses:
    /// - a form with no `never` body, since a pick with no never is written
    ///   with `ONE` marks;
    /// - at a `never` body, a body that holds fewer than two positive atoms
    ///   of the relation of the first positive atom of the `from` clause;
    /// - a form whose every `never` body states only that some columns
    ///   determine a row of the pick, which `ONE` marks state, as
    ///   `states_one` gives.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        refusals(input, &|_| true)
    }

    /// The check over each clause and each `CHOOSE` form once it ends: a
    /// mark follows the body of its clause, and the checks of a `CHOOSE`
    /// form are decided at its `END` (`docs/engine/synthesis.md#token-mask`).
    /// A form of a `DEMO_RULE` ends at its own `END`. An atom that reads
    /// `ONE` is refused once it is written. A clause whose `SET` mark is
    /// written is refused at that mark, since the mark follows the clause's
    /// keyword, proposers and body.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        let open = |at: &[PathStep]| prefix.open.is_some_and(|open| open.0.starts_with(at));
        let set = |at: &NodePath| matches!(node_at(NodeRef::from(prefix.partial), at), Some(NodeRef::Clause(clause)) if clause.set);
        super::prefix::standing(prefix, refusals(&super::prefix::whole(prefix), &|at| !open(at)), &|at| !prefix.is_open(at) || set(at))
    }
}

/// The refusals of [`PicksCheck`] on the form of `input`, those of the `ONE`
/// marks of a clause and of a `CHOOSE` form only where `ended` holds at its
/// path, where that clause or form is written whole.
fn refusals(input: &CheckInput<'_>, ended: &dyn Fn(&[PathStep]) -> bool) -> CheckResult {
    let (form, registry) = (input.form, input.scope.registry);
    let mut refused: Vec<(NodePath, &str)> = Vec::new();
    each_node(NodeRef::from(form), &NodePath::default(), &mut |node, at| match (node, node.atom()) {
        (NodeRef::Clause(clause), _) if ended(at) && !marks_name_columns(clause) => refused.push((at.into(), "a `ONE` mark names only columns of the clause")),
        (NodeRef::Clause(clause), _) if !set_mark_fits(clause, registry) => refused.push((at.into(), set_mark_refusal(clause))),
        (NodeRef::Choose(choose), _) if ended(at) => choose_refusals(choose, &NodePath::from(at), &mut refused),
        (_, Some(Atom { relation: RelationRef::Lib(name), .. })) if *name.0 == *crate::read::spelling::ONE => {
            refused.push((at.into(), "`ONE` stands at a clause's top level, after its body"));
        }
        _ => {}
    });
    if refused.is_empty() {
        return CheckResult::Pass;
    }
    result(refused.into_iter().map(|(at, message)| Refusal { message: message.into(), at: input.refusal_path(&at) }).collect())
}

/// Whether the `SET` mark of `clause`, if it has one, stands after a body of
/// no conjunct and proposers that have one column each and that the registry
/// does not mark `domain`.
fn set_mark_fits(clause: &Clause, registry: &Registry) -> bool {
    let one_column = |name: &LibName| !is_domain(registry, name) && proposer_columns(registry, name).is_some_and(|columns| columns.len() == 1);
    !clause.set || (clause.keyword != ClauseKeyword::Rule && clause.body.value().conjuncts.is_empty() && !clause.proposers.is_empty() && clause.proposers.iter().all(one_column))
}

/// Why the `SET` mark of `clause`, which [`set_mark_fits`] refuses, is
/// refused (`docs/arclog/arclog.md#open-values`).
fn set_mark_refusal(clause: &Clause) -> &'static str {
    if clause.keyword == ClauseKeyword::Rule {
        "a `SET` mark stands on a `DET`, and on no `RULE`"
    } else if !clause.body.value().conjuncts.is_empty() || clause.proposers.is_empty() {
        "a `SET` mark stands only on a clause of no body, after its proposers"
    } else {
        "a `SET` mark stands only after proposers of one column each that the registry does not mark `domain`"
    }
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
        out.push((at.clone(), "every `never` says only that some columns determine a row of the pick, and none pairs two `for` rows at one value of a candidate column, so `ONE` marks state the pick"));
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
/// differ, where the two atoms join at no site of a candidate column or
/// differ at no site of a `for` column. Two atoms that join at a candidate
/// column and differ at a `for` column say that a value of that column
/// stands in at most one row, which no `ONE` mark states, as a `ONE` mark
/// keeps exactly one row for each value of its key. A form with no `never`
/// body is such a pick.
fn states_one(choose: &Choose) -> bool {
    let [Conjunct::Atom(candidate)] = &choose.from.value().conjuncts[..] else { return false };
    let candidate = candidate.value();
    let Some(sites) = site_labels(candidate) else { return false };
    let keys: Vec<&SiteKey<'_>> = sites.iter().map(|(key, _)| key).collect();
    let row_labels: Vec<LabelId> = choose.rows.iter().flat_map(|rows| rows.columns.iter().map(|column| column.label)).collect();
    let row_key = |key: &SiteKey<'_>| sites.iter().any(|(own, label)| own == key && row_labels.contains(label));
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
        let (mut joins_candidate, mut differs_at_row) = (false, false);
        for (key, label) in &first {
            let other = second.iter().find(|(own, _)| own == key).map(|(_, label)| *label).expect("the two atoms have the same sites");
            if other == *label {
                joins_candidate |= !row_key(key);
            } else {
                differs_at_row |= row_key(key);
                differ.push(pair(*label, other));
            }
        }
        if joins_candidate && differs_at_row {
            return false;
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
