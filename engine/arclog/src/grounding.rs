//! The grounding of the labels of a body, which the grounding check and the
//! derivation of a relation macro's modes both apply.

use crate::hash::StableHashSet;
use crate::program::{Atom, Body, Conjunct, Constraint, ConstraintOp, LabelId, Negated, Node, Operand, Site};
use crate::registry::Mode;
use crate::types::{each_conjunct, ValueType};

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
/// A label that stands only in a part of a form, a branch of an `OR`, the
/// test and the then of an `IF`, its else, or the two lists of an `ALL`, and
/// that `outside` does not hold, is grounded where that part grounds it from
/// the labels grounded outside it. `outside` holds the labels that the
/// body's context names outside the body: a clause's head labels, or a
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
    each_conjunct(body, &mut |conjunct| own_labels(conjunct, &mut labels));
    labels
}

struct Walk<'a, 'm> {
    modes: &'a dyn Fn(&Atom) -> &'m [Mode],
    types: &'a dyn Fn(LabelId) -> Option<ValueType>,
}

impl Walk<'_, '_> {
    /// The labels of the conjuncts `list` grounded from `outer`: those that
    /// [`Walk::exported`] gives, and each label that stands only in a part
    /// of a form of `list`, and in none of the labels `outside` holds, where
    /// that part grounds it.
    fn grounded(&self, list: &[&Conjunct], outer: &StableHashSet<LabelId>, outside: &StableHashSet<LabelId>) -> StableHashSet<LabelId> {
        let mut grounded = self.exported(list, outer);
        let mut local = Vec::new();
        for (i, conjunct) in list.iter().enumerate() {
            let parts = parts(conjunct);
            let mut around = outside.clone();
            list.iter().enumerate().filter(|&(k, _)| k != i).for_each(|(_, other)| conjunct_labels(other, &mut around));
            for (j, part) in parts.iter().enumerate() {
                let mut part_outside = around.clone();
                parts.iter().enumerate().filter(|&(k, _)| k != j).flat_map(|(_, other)| other).for_each(|other| conjunct_labels(other, &mut part_outside));
                let inner = self.grounded(part, &grounded, &part_outside);
                local.extend(inner.into_iter().filter(|label| !part_outside.contains(label)));
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
                let mut branches = parts(conjunct).into_iter().map(|part| self.exported(&part, grounded));
                let first = branches.next().expect("an `OR` or an `IF` has a branch");
                let shared: Vec<LabelId> = branches.fold(first, |shared, branch| shared.into_iter().filter(|label| branch.contains(label)).collect()).into_iter().collect();
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

/// The parts of a form, each a list of conjuncts: the branches of an `OR`,
/// the test with the then and the else of an `IF`, and the two lists of an
/// `ALL` together. A `NOT` of a form has that form's parts, and an atom and
/// a constraint have none.
fn parts(conjunct: &Conjunct) -> Vec<Vec<&Conjunct>> {
    fn list<'c>(bodies: &[&'c Node<Body>]) -> Vec<&'c Conjunct> {
        bodies.iter().flat_map(|body| body.value().conjuncts.iter()).collect()
    }
    match conjunct {
        Conjunct::Or(branches) => branches.iter().map(|branch| list(&[branch])).collect(),
        Conjunct::If { test, then, otherwise } => vec![list(&[test, then]), list(&[otherwise])],
        Conjunct::All { domain, body } => vec![list(&[domain, body])],
        Conjunct::Not(Negated::Form(form)) => parts(form),
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
        Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => atom.value().sites.iter().for_each(|site| site_labels(site, labels)),
        Conjunct::Constraint(Constraint { first, second, .. }) => {
            labels.extend([first.label]);
            if let Operand::Label(second) = second {
                labels.extend([second.label]);
            }
        }
        Conjunct::Not(Negated::Form(form)) => own_labels(form, labels),
        Conjunct::Or(_) | Conjunct::If { .. } | Conjunct::All { .. } => {}
    }
}

/// Adds each label at `site`, its fields' included, to `labels`.
fn site_labels(site: &Site, labels: &mut impl Extend<LabelId>) {
    crate::types::each_site_label(site, &mut Vec::new(), &mut |use_, _| {
        labels.extend(crate::types::use_label(use_));
    });
}

/// Whether `ty` is an orientation type, whose label counts as grounded.
fn is_orientation(ty: &ValueType) -> bool {
    match ty {
        ValueType::C4
        | ValueType::D4
        | ValueType::Dir
        | ValueType::DiagDir
        | ValueType::Dir8
        | ValueType::Axis
        | ValueType::DiagAxis
        | ValueType::Axis4
        | ValueType::Sym
        | ValueType::Sense => true,
        ValueType::Number | ValueType::Color | ValueType::Example | ValueType::Unit | ValueType::Box | ValueType::Ident | ValueType::Pose(_) | ValueType::Record(_) => false,
    }
}
