//! The labels of a body that are bound, which the safety check and the
//! derivation of a relation macro's modes both apply.

use crate::hash::StableHashSet;
use crate::program::path::{NodePath, NodeRef};
use crate::program::{constraint_second, Atom, Body, Conjunct, Constraint, ConstraintOp, LabelId, LabelUse, Negated, Node, Operand, Site};
use crate::registry::Mode;
use crate::types::{each_site_label, use_label, ValueType};

/// The labels that `body` binds where the labels of `bound` are
/// bound, those of `bound` included.
///
/// The rule is the clause's, as `docs/arclog/arclog.md#negation-and-constraints`,
/// `docs/arclog/arclog.md#disjunction`, `docs/arclog/arclog.md#conditional`
/// and `docs/arclog/arclog.md#universal` give it, and the order of the
/// conjuncts plays no part in it:
///
/// - A positive atom binds every label at its sites where `modes` gives its
///   relation no mode, and otherwise once the labels at the sites of the
///   columns of one of its modes are bound. A site of `0` counts as
///   bound, and a column at which the atom has no site does not.
/// - A negated atom, a `NOT` of a form, an `ALL` form and a constraint other
///   than `=` bind no label outside themselves.
/// - `(= X Y)` binds each of its labels once the other is bound, and
///   `(= X 0)` binds X.
/// - An `OR` binds the labels that each of its branches binds, and an
///   `IF` the labels that its test with its then and its else each bind.
/// - A label to which `types` gives an orientation type counts as bound.
///
/// A label that stands only in parts of a form, the branches of an `OR`, the
/// test with the then of an `IF` and its else, or the two lists of an `ALL`
/// together, and that `outside` does not hold, is local to each part that
/// holds it. It is bound where every part that holds it binds it from
/// the labels bound outside the form, so a part that holds it only in a
/// negated atom or a constraint other than `=` leaves it unbound. `outside` holds the labels that stand in
/// the body's context outside the body: a clause's head labels, or a
/// relation macro's column labels. Each of them is an outer label of each
/// form of `body` where it stands, so a form binds it for the body only by
/// the rule above for that form, and never as a label local to a part.
pub fn bound_labels<'m>(
    list: &[&Conjunct],
    bound: &StableHashSet<LabelId>,
    outside: &StableHashSet<LabelId>,
    modes: &dyn Fn(&Atom) -> &'m [Mode],
    types: &dyn Fn(LabelId) -> Option<ValueType>,
) -> StableHashSet<LabelId> {
    Walk { modes, types }.bound_in(list, bound, outside)
}

/// The labels that stand in `conjunct`, at any depth.
pub(crate) fn conjunct_label_set(conjunct: &Conjunct) -> StableHashSet<LabelId> {
    let mut labels = StableHashSet::default();
    conjunct_labels(conjunct, &mut labels);
    labels
}

/// For each label, the number of the conjuncts of a list that hold it, so
/// the labels of the other conjuncts of the list come from the labels of
/// each conjunct taken once.
pub(crate) struct LabelCounts(crate::hash::StableHashMap<LabelId, usize>);

impl LabelCounts {
    pub(crate) fn of<'s>(sets: impl IntoIterator<Item = &'s StableHashSet<LabelId>>) -> Self {
        let mut counts = Self(crate::hash::StableHashMap::default());
        sets.into_iter().for_each(|set| counts.add(set));
        counts
    }

    pub(crate) fn add(&mut self, set: &StableHashSet<LabelId>) {
        for label in set {
            *self.0.entry(*label).or_insert(0) += 1;
        }
    }

    pub(crate) fn remove(&mut self, set: &StableHashSet<LabelId>) {
        for label in set {
            if let Some(count) = self.0.get_mut(label) {
                *count -= 1;
            }
        }
    }

    /// `outside` with each label that a conjunct holds other than the one
    /// whose labels are `except`.
    pub(crate) fn around(&self, outside: &StableHashSet<LabelId>, except: Option<&StableHashSet<LabelId>>) -> StableHashSet<LabelId> {
        let mut around = outside.clone();
        around.extend(self.0.iter().filter(|&(label, &count)| count > usize::from(except.is_some_and(|set| set.contains(label)))).map(|(label, _)| *label));
        around
    }
}

/// Each label that stands in `body`, at any depth.
pub(crate) fn body_labels(body: &Body) -> StableHashSet<LabelId> {
    let mut labels = StableHashSet::default();
    each_label_use(body, &mut |use_| labels.extend(use_label(use_)));
    labels
}

/// Visits each label use of `body`, at any depth, in source order.
pub(crate) fn each_label_use(body: &Body, visit: &mut dyn FnMut(LabelUse)) {
    each_label_use_at(NodeRef::Body(body), &NodePath::default(), &mut |_, use_| visit(use_));
}

/// Visits each label use of `node`, at `at`, at any depth, in source
/// order, with its path: a use at a site at the path of its label, and a
/// constraint's at the path of the constraint.
pub(crate) fn each_label_use_at(node: NodeRef<'_>, at: &NodePath, visit: &mut dyn FnMut(&NodePath, LabelUse)) {
    match node {
        NodeRef::Label(use_) => visit(at, *use_),
        NodeRef::Conjunct(Conjunct::Constraint(constraint)) => {
            visit(at, constraint.first.into());
            if let Some(second) = constraint_second(constraint) {
                visit(at, second.into());
            }
        }
        _ => {
            for (child, index) in node.children().into_iter().zip(0u32..) {
                each_label_use_at(child, &at.child(index), visit);
            }
        }
    }
}

/// Visits each label use at the sites of `conjunct` itself, in the order
/// of its sites: an atom's, a negated atom's and a constraint's. A conjunct
/// of another kind has no sites of its own.
pub(crate) fn site_label_uses(conjunct: &Conjunct, visit: &mut dyn FnMut(LabelUse)) {
    if let Some(atom) = conjunct.atom() {
        for site in atom.value().sites.iter() {
            each_site_label(site, &mut Vec::new(), &mut |use_, _| visit(use_));
        }
    } else if let Conjunct::Constraint(constraint) = conjunct {
        visit(constraint.first.into());
        if let Some(second) = constraint_second(constraint) {
            visit(second.into());
        }
    }
}

struct Walk<'a, 'm> {
    modes: &'a dyn Fn(&Atom) -> &'m [Mode],
    types: &'a dyn Fn(LabelId) -> Option<ValueType>,
}

impl Walk<'_, '_> {
    /// The labels that are bound in the conjuncts `list` from `outer`: those that
    /// [`Walk::exported`] gives, and each label that stands only in parts of
    /// a form of `list`, and in none of the labels `outside` holds, where
    /// every part that holds it binds it.
    fn bound_in(&self, list: &[&Conjunct], outer: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>) -> StableHashSet<LabelId> {
        let mut bound = self.exported(list, outer);
        let mut local = Vec::new();
        let sets: Vec<StableHashSet<LabelId>> = list.iter().map(|conjunct| conjunct_label_set(conjunct)).collect();
        let counts = LabelCounts::of(&sets);
        for (i, conjunct) in list.iter().enumerate() {
            let around = counts.around(outside, Some(&sets[i]));
            let per_part: Vec<(StableHashSet<LabelId>, StableHashSet<LabelId>)> = parts(conjunct)
                .iter()
                .map(|part| {
                    let mut held = StableHashSet::default();
                    part.iter().for_each(|inner| conjunct_labels(inner, &mut held));
                    held.retain(|label| !around.contains(label));
                    (self.bound_in(part, &bound, &around), held)
                })
                .collect();
            for (_, held) in &per_part {
                local.extend(held.iter().copied().filter(|label| {
                    per_part.iter().all(|(inner, holds)| !holds.contains(label) || inner.contains(label))
                }));
            }
        }
        bound.extend(local);
        bound
    }

    /// The labels that the conjuncts `list` bind for the scope around
    /// them, from `outer`, its orientation labels and the labels of `outer`
    /// included.
    fn exported(&self, list: &[&Conjunct], outer: &StableHashSet<LabelId>) -> StableHashSet<LabelId> {
        let mut labels = StableHashSet::default();
        list.iter().for_each(|conjunct| conjunct_labels(conjunct, &mut labels));
        let mut bound = outer.clone();
        bound.extend(labels.into_iter().filter(|&label| (self.types)(label).as_ref().is_some_and(is_orientation)));
        loop {
            let before = bound.len();
            for conjunct in list {
                self.bind(conjunct, &mut bound);
            }
            if bound.len() == before {
                return bound;
            }
        }
    }

    /// Adds to `bound` the labels that `conjunct` binds from it.
    fn bind(&self, conjunct: &Conjunct, bound: &mut StableHashSet<LabelId>) {
        match conjunct {
            Conjunct::Atom(atom) => {
                let atom = atom.value();
                if mode_holds(atom, bound, (self.modes)(atom)) {
                    atom.sites.iter().for_each(|site| site_labels(site, bound));
                }
            }
            Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, second }) => match second {
                Operand::Zero => {
                    bound.insert(first.label);
                }
                Operand::Label(second) => {
                    if bound.contains(&first.label) || bound.contains(&second.label) {
                        bound.extend([first.label, second.label]);
                    }
                }
            },
            Conjunct::Constraint(_) | Conjunct::Not(_) | Conjunct::All { .. } => {}
            Conjunct::Or(_) | Conjunct::If { .. } => {
                let shared = common_to_all(parts(conjunct).into_iter().map(|part| self.exported(&part, bound)));
                bound.extend(shared);
            }
        }
    }
}

/// Whether `atom` binds its labels where `bound` are bound, given the
/// `modes` of its relation: there is no mode, or every label at the sites
/// of one mode's columns is bound.
pub(crate) fn mode_holds(atom: &Atom, bound: &StableHashSet<LabelId>, modes: &[Mode]) -> bool {
    modes.is_empty()
        || modes.iter().any(|mode| {
            mode.bound.iter().all(|column| {
                atom.sites.iter().find(|site| &site.column == column).is_some_and(|site| {
                    let mut labels = StableHashSet::default();
                    site_labels(site, &mut labels);
                    labels.iter().all(|label| bound.contains(label))
                })
            })
        })
}

/// The labels at the sites of `atom` to which `types` gives an orientation
/// type, which count as bound.
pub(crate) fn orientation_labels(atom: &Atom, types: &dyn Fn(LabelId) -> Option<ValueType>) -> StableHashSet<LabelId> {
    let mut labels = StableHashSet::default();
    atom.sites.iter().for_each(|site| site_labels(site, &mut labels));
    labels.retain(|&label| types(label).as_ref().is_some_and(is_orientation));
    labels
}

/// The labels that an `OR` or an `IF` binds, from `per_branch`, the labels
/// each of its branches binds: those that every branch binds.
pub(crate) fn common_to_all(per_branch: impl IntoIterator<Item = StableHashSet<LabelId>>) -> StableHashSet<LabelId> {
    let mut branches = per_branch.into_iter();
    let first = branches.next().expect("an `OR` or an `IF` has a branch");
    branches.fold(first, |shared, branch| shared.into_iter().filter(|label| branch.contains(label)).collect())
}

/// The parts of a form, each a list of conjuncts: those [`parts_of`]
/// gives, where a `NOT` of a form has that form's parts.
fn parts(conjunct: &Conjunct) -> Vec<Vec<&Conjunct>> {
    match conjunct {
        Conjunct::Not(Negated::Form(form)) => parts(form),
        _ => parts_of(conjunct, &NodePath::default()).into_iter().map(|part| part.into_iter().map(|(_, inner)| inner).collect()).collect(),
    }
}

/// The conjuncts of `body`, at `at`, each with its path.
pub(crate) fn list_of<'a>(body: &'a Body, at: &NodePath) -> Vec<(NodePath, &'a Conjunct)> {
    body.conjuncts.iter().zip(0u32..).map(|(conjunct, index)| (at.child(index), conjunct)).collect()
}

/// The parts of `conjunct`, at `at`, each a list of conjuncts with their
/// paths: the branches of an `OR`, the test with the then and the else of
/// an `IF`, the two lists of an `ALL` together, and the inner form of a
/// `NOT` as a list of its own. An atom and a constraint have none.
pub(crate) fn parts_of<'a>(conjunct: &'a Conjunct, at: &NodePath) -> Vec<Vec<(NodePath, &'a Conjunct)>> {
    let lists = |bodies: &[(&'a Node<Body>, u32)]| bodies.iter().flat_map(|(body, index)| list_of(body.value(), &at.child(*index))).collect();
    match conjunct {
        Conjunct::Or(branches) => branches.iter().zip(0u32..).map(|(branch, index)| lists(&[(branch, index)])).collect(),
        Conjunct::If { test, then, otherwise } => vec![lists(&[(test, 0), (then, 1)]), lists(&[(otherwise, 2)])],
        Conjunct::All { domain, body } => vec![lists(&[(domain, 0), (body, 1)])],
        Conjunct::Not(Negated::Form(form)) => vec![vec![(at.child(0), &**form)]],
        Conjunct::Atom(_) | Conjunct::Not(Negated::Atom(_)) | Conjunct::Constraint(_) => Vec::new(),
    }
}

/// Adds each label that stands in `conjunct`, at any depth, to `labels`.
pub(crate) fn conjunct_labels(conjunct: &Conjunct, labels: &mut StableHashSet<LabelId>) {
    own_labels(conjunct, labels);
    for part in parts(conjunct) {
        part.into_iter().for_each(|inner| conjunct_labels(inner, labels));
    }
}

/// Adds the labels of `conjunct` that stand outside its parts to `labels`,
/// in the order of its sites: an atom's, a negated atom's and a
/// constraint's.
pub(crate) fn own_labels(conjunct: &Conjunct, labels: &mut impl Extend<LabelId>) {
    match conjunct {
        Conjunct::Not(Negated::Form(form)) => own_labels(form, labels),
        _ => site_label_uses(conjunct, &mut |use_| labels.extend(use_label(use_))),
    }
}

/// Adds each label at `site`, its fields' included, to `labels`.
fn site_labels(site: &Site, labels: &mut impl Extend<LabelId>) {
    each_site_label(site, &mut Vec::new(), &mut |use_, _| labels.extend(use_label(use_)));
}

/// Whether `ty` is an orientation type, whose label counts as bound.
fn is_orientation(ty: &ValueType) -> bool {
    ty.orientation_types().is_some()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::layout::SourceFile;
    use crate::read::{read_body, read_sexprs};

    /// The number of labels of the body `text` that [`bound_labels`]
    /// leaves unbound, where no label is bound before and no
    /// relation has a mode.
    fn unsafe_count(text: &str) -> usize {
        let (exprs, _) = read_sexprs(text, SourceFile::Arclog).expect("the body parses");
        let (body, _) = read_body(&exprs).expect("the body reads");
        let body = body.value();
        let none = StableHashSet::default();
        let bound = bound_labels(&body.conjuncts.iter().collect::<Vec<_>>(), &none, &none, &|_| &[], &|_| None);
        body_labels(body).iter().filter(|label| !bound.contains(label)).count()
    }

    #[test]
    fn a_label_in_two_branches_that_both_bind_it_is_bound() {
        assert_eq!(unsafe_count("(input (:P *Q) *Col) (OR ((input *P Col)) ((input (:P Q) Col)) ((input P Col)))"), 0);
        assert_eq!(unsafe_count("(&a *Z) (OR ((&r *X)) ((&s *X)) ((&t Z)))"), 0);
    }

    #[test]
    fn a_label_of_another_conjunct_is_left_to_the_export_rule() {
        assert_eq!(unsafe_count("(NOT (&u *X)) (OR ((&r X)) ((&s X)) ((&t *Y)))"), 1);
    }

    #[test]
    fn a_branch_that_holds_the_label_only_in_a_negated_atom_or_a_comparison_leaves_it_unsafe() {
        assert_eq!(unsafe_count("(OR ((NOT (&s *X))) ((&r X)))"), 1);
        assert_eq!(unsafe_count("(&a *Z) (OR ((< *X Z)) ((&r X)))"), 1);
    }

    #[test]
    fn a_label_in_the_then_and_the_else_of_an_if_is_bound_where_both_bind_it() {
        assert_eq!(unsafe_count("(&a *Z) (IF ((&p Z)) ((&q *X)) ((&r X)))"), 0);
        assert_eq!(unsafe_count("(&a *Z) (IF ((&p Z)) ((&q *X)) ((NOT (&r X))))"), 1);
    }

    #[test]
    fn a_label_that_the_first_list_of_an_all_makes_is_bound_for_the_second() {
        assert_eq!(unsafe_count("(ALL ((&r *X)) ((&s X)))"), 0);
    }
}
