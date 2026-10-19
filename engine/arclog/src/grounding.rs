//! The grounding of the labels of a body, which the grounding check and the
//! derivation of a relation macro's modes both apply.

use crate::hash::StableHashSet;
use crate::program::path::{NodePath, NodeRef};
use crate::program::{constraint_second, Atom, Body, Conjunct, Constraint, ConstraintOp, LabelId, LabelUse, Negated, Node, Operand, Site};
use crate::registry::Mode;
use crate::types::{each_site_label, use_label, ValueType};

/// The labels that `body` grounds where the labels of `grounded` are
/// grounded, those of `grounded` included.
///
/// The rule is the clause's, as `docs/arclog/arclog.md#negation-and-constraints`,
/// `docs/arclog/arclog.md#disjunction`, `docs/arclog/arclog.md#conditional`
/// and `docs/arclog/arclog.md#universal` give it, and the order of the
/// conjuncts plays no part in it:
///
/// - A positive atom grounds every label at its sites where `modes` gives its
///   relation no mode, and otherwise once the labels at the sites of the
///   columns of one of its modes are grounded. A site of `0` counts as
///   grounded, and a column at which the atom has no site does not.
/// - A negated atom, a `NOT` of a form, an `ALL` form and a constraint other
///   than `=` ground no label outside themselves.
/// - `(= X Y)` grounds each of its labels once the other is grounded, and
///   `(= X 0)` grounds X.
/// - An `OR` grounds the labels that each of its branches grounds, and an
///   `IF` the labels that its test with its then and its else each ground.
/// - A label to which `types` gives an orientation type counts as grounded.
///
/// A label that stands only in parts of a form, the branches of an `OR`, the
/// test with the then of an `IF` and its else, or the two lists of an `ALL`
/// together, and that `outside` does not hold, is local to each part that
/// holds it. It is grounded where every part that holds it grounds it from
/// the labels grounded outside the form, so a part that holds it only in a
/// negated atom or a constraint other than `=` leaves it ungrounded. `outside` holds the labels that stand in
/// the body's context outside the body: a clause's head labels, or a
/// relation macro's column labels. Each of them is an outer label of each
/// form of `body` where it stands, so a form grounds it for the body only by
/// the rule above for that form, and never as a label local to a part.
pub fn grounded_labels<'m>(
    body: &Body,
    grounded: &StableHashSet<LabelId>,
    outside: &StableHashSet<LabelId>,
    modes: &dyn Fn(&Atom) -> &'m [Mode],
    types: &dyn Fn(LabelId) -> Option<ValueType>,
) -> StableHashSet<LabelId> {
    let list: Vec<&Conjunct> = body.conjuncts.iter().collect();
    Walk { modes, types }.grounded(&list, grounded, outside)
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
    /// The labels of the conjuncts `list` grounded from `outer`: those that
    /// [`Walk::exported`] gives, and each label that stands only in parts of
    /// a form of `list`, and in none of the labels `outside` holds, where
    /// every part that holds it grounds it.
    fn grounded(&self, list: &[&Conjunct], outer: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>) -> StableHashSet<LabelId> {
        let mut grounded = self.exported(list, outer);
        let mut local = Vec::new();
        for (i, conjunct) in list.iter().enumerate() {
            let mut around = outside.clone();
            list.iter().enumerate().filter(|&(k, _)| k != i).for_each(|(_, other)| conjunct_labels(other, &mut around));
            let per_part: Vec<(StableHashSet<LabelId>, StableHashSet<LabelId>)> = parts(conjunct)
                .iter()
                .map(|part| {
                    let mut held = StableHashSet::default();
                    part.iter().for_each(|inner| conjunct_labels(inner, &mut held));
                    held.retain(|label| !around.contains(label));
                    (self.grounded(part, &grounded, &around), held)
                })
                .collect();
            for (_, held) in &per_part {
                local.extend(held.iter().copied().filter(|label| {
                    per_part.iter().all(|(inner, holds)| !holds.contains(label) || inner.contains(label))
                }));
            }
        }
        grounded.extend(local);
        grounded
    }

    /// The labels that the conjuncts `list` ground for the scope around
    /// them, from `outer`, its orientation labels and the labels of `outer`
    /// included.
    fn exported(&self, list: &[&Conjunct], outer: &StableHashSet<LabelId>) -> StableHashSet<LabelId> {
        let mut labels = StableHashSet::default();
        list.iter().for_each(|conjunct| conjunct_labels(conjunct, &mut labels));
        let mut grounded = outer.clone();
        grounded.extend(labels.into_iter().filter(|&label| (self.types)(label).as_ref().is_some_and(is_orientation)));
        loop {
            let before = grounded.len();
            for conjunct in list {
                self.ground(conjunct, &mut grounded);
            }
            if grounded.len() == before {
                return grounded;
            }
        }
    }

    /// Adds to `grounded` the labels that `conjunct` grounds from it.
    fn ground(&self, conjunct: &Conjunct, grounded: &mut StableHashSet<LabelId>) {
        match conjunct {
            Conjunct::Atom(atom) => {
                let atom = atom.value();
                if self.mode_holds(atom, grounded) {
                    atom.sites.iter().for_each(|site| site_labels(site, grounded));
                }
            }
            Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, second }) => match second {
                Operand::Zero => {
                    grounded.insert(first.label);
                }
                Operand::Label(second) => {
                    if grounded.contains(&first.label) || grounded.contains(&second.label) {
                        grounded.extend([first.label, second.label]);
                    }
                }
            },
            Conjunct::Constraint(_) | Conjunct::Not(_) | Conjunct::All { .. } => {}
            Conjunct::Or(_) | Conjunct::If { .. } => {
                let shared = common_to_all(parts(conjunct).into_iter().map(|part| self.exported(&part, grounded)));
                grounded.extend(shared);
            }
        }
    }

    /// Whether `atom` grounds its labels where `grounded` are grounded: its
    /// relation has no mode, or every label at the sites of one mode's
    /// columns is grounded.
    fn mode_holds(&self, atom: &Atom, grounded: &StableHashSet<LabelId>) -> bool {
        let modes = (self.modes)(atom);
        modes.is_empty()
            || modes.iter().any(|mode| {
                mode.grounded.iter().all(|column| {
                    atom.sites.iter().find(|site| &site.column == column).is_some_and(|site| {
                        let mut labels = StableHashSet::default();
                        site_labels(site, &mut labels);
                        labels.iter().all(|label| grounded.contains(label))
                    })
                })
            })
    }
}

/// The labels that an `OR` or an `IF` grounds, from `per_branch`, the labels
/// each of its branches grounds: those that every branch grounds.
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

/// Whether `ty` is an orientation type, whose label counts as grounded.
fn is_orientation(ty: &ValueType) -> bool {
    ty.orientation_types().is_some()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::layout::SourceFile;
    use crate::read::{read_body, read_sexprs};

    /// The number of labels of the body `text` that [`grounded_labels`]
    /// leaves ungrounded, where no label is grounded before and no
    /// relation has a mode.
    fn ungrounded(text: &str) -> usize {
        let (exprs, _) = read_sexprs(text, SourceFile::Arclog).expect("the body parses");
        let (body, _) = read_body(&exprs).expect("the body reads");
        let body = body.value();
        let none = StableHashSet::default();
        let grounded = grounded_labels(body, &none, &none, &|_| &[], &|_| None);
        body_labels(body).iter().filter(|label| !grounded.contains(label)).count()
    }

    #[test]
    fn a_label_in_two_branches_that_both_ground_it_is_grounded() {
        assert_eq!(ungrounded("(input (:P *Q) *Col) (OR ((input *P Col)) ((input (:P Q) Col)) ((input P Col)))"), 0);
        assert_eq!(ungrounded("(&a *Z) (OR ((&r *X)) ((&s *X)) ((&t Z)))"), 0);
    }

    #[test]
    fn a_label_of_another_conjunct_is_left_to_the_export_rule() {
        assert_eq!(ungrounded("(NOT (&u *X)) (OR ((&r X)) ((&s X)) ((&t *Y)))"), 1);
    }

    #[test]
    fn a_branch_that_holds_the_label_only_in_a_negated_atom_or_a_comparison_leaves_it_ungrounded() {
        assert_eq!(ungrounded("(OR ((NOT (&s *X))) ((&r X)))"), 1);
        assert_eq!(ungrounded("(&a *Z) (OR ((< *X Z)) ((&r X)))"), 1);
    }

    #[test]
    fn a_label_in_the_then_and_the_else_of_an_if_is_grounded_where_both_ground_it() {
        assert_eq!(ungrounded("(&a *Z) (IF ((&p Z)) ((&q *X)) ((&r X)))"), 0);
        assert_eq!(ungrounded("(&a *Z) (IF ((&p Z)) ((&q *X)) ((NOT (&r X))))"), 1);
    }

    #[test]
    fn a_label_that_the_first_list_of_an_all_makes_is_grounded_for_the_second() {
        assert_eq!(ungrounded("(ALL ((&r *X)) ((&s X)))"), 0);
    }
}
