//! Proven local atom laws. See `static_prune/proofs.md` for the implementation
//! arguments. This module does not evaluate rows or infer a type from the
//! candidate it is classifying. Callers supply types from existing bindings.
use super::*;
use crate::types::ValueType;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Class {
    Unsatisfiable,
    Valid,
    Alias,
    Constant,
}
impl Class {
    pub fn name(self) -> &'static str {
        match self {
            Self::Unsatisfiable => "unsatisfiable",
            Self::Valid => "valid",
            Self::Alias => "alias",
            Self::Constant => "constant",
        }
    }
}
/// The conclusion and an equality candidate where the language can express
/// it. This is a proposal, not a certificate of interface or frame equivalence.
#[derive(Clone, Debug)]
pub struct Verdict {
    pub class: Class,
    pub rule: &'static str,
    pub replacement: Option<Constraint>,
}
fn verdict(class: Class, rule: &'static str) -> Verdict {
    Verdict {
        class,
        rule,
        replacement: None,
    }
}

/// Exact positive-read idempotence. The earlier occurrence may bind a label;
/// the later one must only read it. Context/lift compatibility is the caller's
/// premise. See "Repeated positive atoms" in the accompanying proof.
pub fn repeated_atom(earlier: &Atom, later: &Atom) -> Option<Verdict> {
    fn label(a: LabelUse, b: LabelUse) -> bool {
        match (a, b) {
            (LabelUse::Zero, LabelUse::Zero) => true,
            (LabelUse::Fresh(a) | LabelUse::Join(a) | LabelUse::Key(a), LabelUse::Join(b)) => a == b,
            _ => false,
        }
    }
    fn arg(a: &SiteArg, b: &SiteArg) -> bool {
        match (a, b) {
            (SiteArg::Label(a), SiteArg::Label(b)) => label(*a, *b),
            (SiteArg::NamedLabel { name: a, label: x }, SiteArg::NamedLabel { name: b, label: y }) => a == b && label(*x, *y),
            (SiteArg::Field(a), SiteArg::Field(b)) => site(a, b),
            _ => false,
        }
    }
    fn unordered<T>(a: &[T], b: &[T], equal: impl Fn(&T, &T) -> bool) -> bool {
        if a.len() != b.len() { return false; }
        let mut used = vec![false; a.len()];
        b.iter().all(|b| {
            let Some(i) = a.iter().enumerate().position(|(i,a)| !used[i] && equal(a,b)) else { return false; };
            used[i] = true;
            true
        })
    }
    fn site(a: &Site, b: &Site) -> bool {
        if a.column != b.column || a.value.args.len() != b.value.args.len() { return false; }
        // Named record fields are unordered; positional labels are ordered.
        if a.value.args.iter().chain(b.value.args.iter()).all(|x| !matches!(x, SiteArg::Label(_))) {
            unordered(&a.value.args, &b.value.args, arg)
        } else {
            a.value.args.iter().zip(b.value.args.iter()).all(|(a,b)| arg(a,b))
        }
    }
    (earlier.relation == later.relation && earlier.sites.len() == later.sites.len()
        && unordered(&earlier.sites, &later.sites, site))
        .then(|| verdict(Class::Valid, "atom.repeated"))
}

/// Types of labels already bound in this lexical scope. This must not be
/// populated with the candidate's inferred meet, or with a later use's type.
/// Key labels use the key's binding column, not an input port's narrowing.
pub type BindingType<'a> = &'a dyn Fn(LabelId) -> Option<ValueType>;

/// Classify one checked conjunct. Negation complements tests only; branch
/// forms are classified by their own callers, never flattened into a body.
pub fn classify(conjunct: &Conjunct, binding: BindingType<'_>) -> Option<Verdict> {
    match conjunct {
        Conjunct::Atom(atom) => classify_atom(atom.value(), binding),
        Conjunct::Constraint(c) => classify_constraint(c, binding),
        Conjunct::Not(Negated::Atom(atom)) => {
            let mut found = classify_atom(atom.value(), binding)?;
            found.class = match found.class {
                Class::Unsatisfiable => Class::Valid,
                Class::Valid => Class::Unsatisfiable,
                _ => return None,
            };
            Some(found)
        }
        _ => None,
    }
}
fn classify_constraint(c: &Constraint, binding: BindingType<'_>) -> Option<Verdict> {
    if c.first.fresh || binding(c.first.label).is_none() {
        return None;
    }
    if let Operand::Label(other) = c.second {
        if other.fresh || other.label != c.first.label {
            return None;
        }
        return Some(match c.op {
            ConstraintOp::Lt | ConstraintOp::Gt | ConstraintOp::Ne => {
                verdict(Class::Unsatisfiable, "comparison.same")
            }
            ConstraintOp::Le | ConstraintOp::Ge | ConstraintOp::Eq => {
                verdict(Class::Valid, "comparison.same")
            }
        });
    }
    if matches!(c.second, Operand::Zero) && binding(c.first.label) == Some(ValueType::Nat) {
        return match c.op {
            ConstraintOp::Lt => Some(verdict(Class::Unsatisfiable, "nat.lt_zero")),
            ConstraintOp::Ge => Some(verdict(Class::Valid, "nat.ge_zero")),
            _ => None,
        };
    }
    None
}
fn label(atom: &Atom, name: &str) -> Option<LabelUse> {
    let site = atom
        .sites
        .iter()
        .find(|s| s.column == ColumnName::Written(name.into()))?;
    if site.value.args.len() != 1 {
        return None;
    }
    match &site.value.args[0] {
        SiteArg::Label(label) => Some(*label),
        _ => None,
    }
}
fn existing(value: LabelUse, binding: BindingType<'_>) -> bool {
    match value {
        LabelUse::Join(id) | LabelUse::Key(id) => binding(id).is_some(),
        LabelUse::Zero => true,
        _ => false,
    }
}
fn same(atom: &Atom, a: &str, b: &str, binding: BindingType<'_>) -> bool {
    matches!((label(atom,a),label(atom,b)),(Some(x),Some(y)) if x==y && existing(x,binding))
}
fn bound(atom: &Atom, names: &[&str], binding: BindingType<'_>) -> bool {
    names
        .iter()
        .all(|name| label(atom, name).is_some_and(|v| existing(v, binding)))
}
fn zero(atom: &Atom, name: &str) -> bool {
    label(atom, name) == Some(LabelUse::Zero)
}
/// A joined finite-domain input must already be wholly inside the relation's
/// domain. Merely having a nonempty type meet would discard a real filter.
/// An omitted input is projected; its nonempty domain introduces no label.
fn admits_orientation(
    atom: &Atom,
    column: &str,
    expected: &ValueType,
    binding: BindingType<'_>,
) -> bool {
    if !atom
        .sites
        .iter()
        .any(|s| s.column == ColumnName::Written(column.into()))
    {
        return true;
    }
    let Some(LabelUse::Join(id) | LabelUse::Key(id)) = label(atom, column) else {
        return false;
    };
    let Some(actual) = binding(id) else {
        return false;
    };
    actual.is_below(expected)
}
fn output(
    atom: &Atom,
    out: &str,
    value: LabelUse,
    class: Class,
    rule: &'static str,
    binding: BindingType<'_>,
) -> Option<Verdict> {
    let LabelUse::Fresh(id) = label(atom, out)? else {
        return None;
    };
    // Do not erase a second new binding or a record/unknown site.
    for site in atom
        .sites
        .iter()
        .filter(|site| site.column != ColumnName::Written(out.into()))
    {
        if site.value.args.len() != 1
            || !site.value.args[0]
                .label()
                .is_some_and(|v| existing(v, binding))
        {
            return None;
        }
    }
    let second = match value {
        LabelUse::Zero => Some(Operand::Zero),
        LabelUse::Join(label) => Some(Operand::Label(ConstraintLabel {
            label,
            fresh: false,
        })),
        // A key-marked label is not a local equality operand. Do not erase
        // its mark by constructing ConstraintLabel from the numeric id.
        LabelUse::Key(_) => None,
        _ => return None,
    };
    Some(Verdict {
        // An identity applied to literal zero produces a constant, not an
        // alias to an existing variable.
        class: if class == Class::Alias && value == LabelUse::Zero {
            Class::Constant
        } else {
            class
        },
        rule,
        replacement: second.map(|second| Constraint {
            op: ConstraintOp::Eq,
            first: ConstraintLabel {
                label: id,
                fresh: true,
            },
            second,
        }),
    })
}
fn classify_atom(atom: &Atom, binding: BindingType<'_>) -> Option<Verdict> {
    let RelationRef::Lib(name) = &atom.relation else {
        return None;
    };
    let name = &*name.0;
    let repeated = match name {
        "interior" => ("A", "B", Class::Unsatisfiable),
        "inside" => ("A", "B", Class::Valid),
        "nearer" | "gap" => ("P", "Q", Class::Unsatisfiable),
        "neighbor" => ("P", "Q", Class::Unsatisfiable),
        "same_dist" | "same_corner" | "same_slab" => ("P1", "P2", Class::Valid),
        "same_line" => ("P", "Q", Class::Valid),
        "opposite" | "diag_opposite" => ("D", "Opp", Class::Unsatisfiable),
        "dir8_opposite" => ("D", "D2", Class::Unsatisfiable),
        "perp" => ("A", "A2", Class::Unsatisfiable),
        "diag_perp" => ("Da", "Da2", Class::Unsatisfiable),
        "perp_dir" => ("D", "D2", Class::Unsatisfiable),
        "turn" => ("D", "D2", Class::Unsatisfiable),
        _ => ("", "", Class::Valid),
    };
    if !repeated.0.is_empty() && same(atom, repeated.0, repeated.1, binding) {
        let domain_admitted = match name {
            "same_dist" | "same_slab" => admits_orientation(atom, "D", &ValueType::Dir, binding),
            "same_corner" => admits_orientation(atom, "D", &ValueType::DiagDir, binding),
            "same_line" => admits_orientation(atom, "A", &ValueType::Axis4, binding),
            _ => true,
        };
        if repeated.2 == Class::Unsatisfiable
            || (domain_admitted
                && atom.sites.iter().all(|site| {
                    site.value.args.len() == 1
                        && site.value.args[0]
                            .label()
                            .is_some_and(|v| existing(v, binding))
                }))
        {
            return Some(verdict(
                repeated.2,
                match name {
                    "interior" => "interior.same",
                    "inside" => "inside.same",
                    "nearer" => "nearer.same",
                    "gap" => "gap.same",
                    "neighbor" => "neighbor.same",
                    "same_dist" => "same_dist.same",
                    "same_line" => "same_line.same",
                    "same_corner" => "same_corner.same",
                    "same_slab" => "same_slab.same",
                    _ => "orientation.no_fixed_point",
                },
            ));
        }
    }
    if name == "divide" && zero(atom, "Side") {
        return Some(verdict(Class::Unsatisfiable, "divide.zero_side"));
    }
    if let Some(tested) = membership_type(name) {
        let site = atom.sites.first()?;
        if atom.sites.len() != 1 || site.value.args.len() != 1 {
            return None;
        }
        let id = match site.value.args[0].label()? {
            LabelUse::Join(id) | LabelUse::Key(id) => id,
            _ => return None,
        };
        let ty = binding(id)?;
        // Use types, never coincident untagged term encodings, to establish
        // disjointness. Pose enumeration is explicitly D4 in Geometry.
        let ty = if matches!(ty, ValueType::Pose(_)) {
            ValueType::D4
        } else {
            ty
        };
        if ty.is_below(&tested) {
            return Some(verdict(Class::Valid, "membership.subtype"));
        }
        if !ty.meets(&tested) {
            return Some(verdict(Class::Unsatisfiable, "membership.disjoint"));
        }
    }
    match name {
        "compose" if zero(atom, "A") => output(
            atom,
            "C",
            label(atom, "B")?,
            Class::Alias,
            "compose.left_zero",
            binding,
        ),
        "compose" if zero(atom, "B") => output(
            atom,
            "C",
            label(atom, "A")?,
            Class::Alias,
            "compose.right_zero",
            binding,
        ),
        "relative" if zero(atom, "Base") => output(
            atom,
            "X_rel",
            label(atom, "X")?,
            Class::Alias,
            "relative.zero_base",
            binding,
        ),
        "relative" if same(atom, "Base", "X", binding) => output(
            atom,
            "X_rel",
            LabelUse::Zero,
            Class::Constant,
            "relative.same",
            binding,
        ),
        "jump"
            if zero(atom, "K")
                && bound(atom, &["P", "D"], binding)
                && admits_orientation(atom, "D", &ValueType::Dir8, binding) =>
        {
            output(
                atom,
                "Q",
                label(atom, "P")?,
                Class::Alias,
                "jump.zero",
                binding,
            )
        }
        "edge_inset" | "edge_outset" | "corner_inset" | "corner_outset" | "uniform_inset"
        | "uniform_outset"
            if zero(atom, "K")
                && match name {
                    "edge_inset" | "edge_outset" => {
                        admits_orientation(atom, "D", &ValueType::Dir, binding)
                    }
                    "corner_inset" | "corner_outset" => {
                        admits_orientation(atom, "Diag", &ValueType::DiagDir, binding)
                    }
                    _ => true,
                } =>
        {
            output(
                atom,
                "B",
                LabelUse::Zero,
                Class::Constant,
                "inset_outset.zero",
                binding,
            )
        }
        "axis_inset" | "axis_outset"
            if zero(atom, "K1")
                && zero(atom, "K2")
                && admits_orientation(atom, "D", &ValueType::Dir, binding) =>
        {
            output(
                atom,
                "B",
                LabelUse::Zero,
                Class::Constant,
                "axis_inset_outset.zero",
                binding,
            )
        }
        "jump_offset"
            if zero(atom, "K") && admits_orientation(atom, "D", &ValueType::Dir8, binding) =>
        {
            output(
                atom,
                "V",
                LabelUse::Zero,
                Class::Constant,
                "jump_offset.zero",
                binding,
            )
        }
        _ => None,
    }
}
fn membership_type(name: &str) -> Option<ValueType> {
    Some(match name {
        "dir_elem" => ValueType::Dir,
        "axis_elem" => ValueType::Axis,
        "diag_dir_elem" => ValueType::DiagDir,
        "diag_axis_elem" => ValueType::DiagAxis,
        "d4_elem" => ValueType::D4,
        "c4_elem" => ValueType::C4,
        "sense_elem" => ValueType::Sense,
        "sym_elem" => ValueType::Sym,
        "dir8_elem" => ValueType::Dir8,
        "axis4_elem" => ValueType::Axis4,
        _ => return None,
    })
}

/// Verdict for the last conjunct of a flat decoder body. The prefix owns its
/// prior binding columns; no completed full-program inference is needed.
/// Nested OR/IF/ALL bindings deliberately give no premise here.
pub fn classify_prefix(
    body: &Body,
    column_type: &dyn Fn(&RelationRef, &ColumnName) -> Option<ValueType>,
) -> Option<Verdict> {
    let (last, earlier) = body.conjuncts.split_last()?;
    let mut bound = std::collections::HashMap::<LabelId, ValueType>::new();
    for conjunct in earlier {
        let Conjunct::Atom(atom) = conjunct else {
            continue;
        };
        for site in atom.value().sites.iter() {
            let [arg] = &site.value.args[..] else {
                continue;
            };
            if let Some(LabelUse::Fresh(label)) = arg.label() {
                if let Some(ty) = column_type(&atom.value().relation, &site.column) {
                    bound.entry(label).or_insert(ty);
                }
            }
        }
    }
    classify(last, &|id| bound.get(&id).cloned())
        .or_else(|| {
            let Conjunct::Atom(last) = last else { return None; };
            earlier.iter().find_map(|prior| match prior {
                Conjunct::Atom(prior) => repeated_atom(prior.value(), last.value()),
                _ => None,
            })
        })
        .or_else(|| against_earlier(last, earlier))
}

/// The value of a site that holds one label: the label, a fresh one as the
/// label it makes, or `0`.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Held {
    Label(LabelId),
    Zero,
}

/// Each site of `atom` as its column, its value and whether it makes its
/// label, as `*` and `^` do, where each site holds one label; None where a
/// site holds a record's fields.
fn held(atom: &Atom) -> Option<Vec<(&ColumnName, Held, bool)>> {
    atom.sites
        .iter()
        .map(|site| match &site.value.args[..] {
            [SiteArg::Label(LabelUse::Fresh(id) | LabelUse::Key(id))] => Some((&site.column, Held::Label(*id), true)),
            [SiteArg::Label(LabelUse::Join(id))] => Some((&site.column, Held::Label(*id), false)),
            [SiteArg::Label(LabelUse::Zero)] => Some((&site.column, Held::Zero, false)),
            _ => None,
        })
        .collect()
}

/// Whether each row that `wider` matches, in one conjunction with `test`,
/// matches `test` too: the two read one relation, `test` makes no label, and
/// each site of `test` stands at a column where `wider` holds the same value.
fn matched_by(test: &Atom, wider: &Atom) -> bool {
    if test.relation != wider.relation {
        return false;
    }
    let (Some(test), Some(wider)) = (held(test), held(wider)) else { return false };
    test.iter().all(|(column, value, fresh)| !fresh && wider.iter().any(|(c, v, _)| c == column && v == value))
}

/// The outcomes of a comparison's first operand against its second that
/// `op` keeps: less (1), equal (2) and greater (4).
fn outcomes(op: ConstraintOp) -> u8 {
    match op {
        ConstraintOp::Lt => 1,
        ConstraintOp::Eq => 2,
        ConstraintOp::Gt => 4,
        ConstraintOp::Le => 3,
        ConstraintOp::Ge => 6,
        ConstraintOp::Ne => 5,
    }
}

/// The outcomes that `earlier` and `later` keep, each of `earlier`'s first
/// operand against its second, where the two compare the same two operands.
fn pair_outcomes(earlier: &Constraint, later: &Constraint) -> Option<(u8, u8)> {
    let operands = |c: &Constraint| {
        let second = match c.second {
            Operand::Label(label) => Held::Label(label.label),
            Operand::Zero => Held::Zero,
        };
        (Held::Label(c.first.label), second)
    };
    let (a, b) = (operands(earlier), operands(later));
    let swapped = |set: u8| (set & 2) | ((set & 1) << 2) | ((set & 4) >> 2);
    if a == b {
        Some((outcomes(earlier.op), outcomes(later.op)))
    } else if a == (b.1, b.0) {
        Some((outcomes(earlier.op), swapped(outcomes(later.op))))
    } else {
        None
    }
}

/// The verdict on `last` that one earlier conjunct of its conjunction gives:
/// an atom that an earlier atom of its relation matches at each of its
/// sites, which holds wherever the earlier one holds; a positive atom and a
/// `NOT` of one relation where the positive one matches the negated one's
/// sites, which no row satisfies; a `NOT` whose sites an earlier `NOT` of its
/// relation matches, which refuses no row the earlier one leaves; and a
/// comparison of the two operands an earlier comparison compares, which the
/// earlier one implies or contradicts.
fn against_earlier(last: &Conjunct, earlier: &[Conjunct]) -> Option<Verdict> {
    match last {
        Conjunct::Atom(atom) => earlier.iter().find_map(|prior| match prior {
            Conjunct::Atom(prior) if matched_by(atom.value(), prior.value()) => Some(verdict(Class::Valid, "atom.implied")),
            Conjunct::Not(Negated::Atom(prior)) if matched_by(prior.value(), atom.value()) => {
                Some(verdict(Class::Unsatisfiable, "not.contradicted"))
            }
            _ => None,
        }),
        Conjunct::Not(Negated::Atom(atom)) => earlier.iter().find_map(|prior| match prior {
            Conjunct::Atom(prior) if matched_by(atom.value(), prior.value()) => Some(verdict(Class::Unsatisfiable, "not.contradicted")),
            Conjunct::Not(Negated::Atom(prior)) if matched_by(prior.value(), atom.value()) => Some(verdict(Class::Valid, "not.implied")),
            _ => None,
        }),
        Conjunct::Constraint(constraint) => earlier.iter().find_map(|prior| {
            let Conjunct::Constraint(prior) = prior else { return None };
            match pair_outcomes(prior, constraint)? {
                (first, second) if first & second == 0 => Some(verdict(Class::Unsatisfiable, "comparison.contradicted")),
                (first, second) if first & !second == 0 => Some(verdict(Class::Valid, "comparison.implied")),
                _ => None,
            }
        }),
        _ => None,
    }
}

/// The rule by which the last conjunct of a flat decoder body makes an
/// earlier conjunct of it redundant, where it does: an atom that matches
/// each site of an earlier atom of its relation that makes no label; a `NOT`
/// that refuses each row an earlier `NOT` of its relation refuses; and a
/// comparison of two operands that an earlier comparison compares, where
/// the two keep fewer outcomes than the earlier one. The conjunction then
/// equals one without the earlier conjunct, or with one comparison of the
/// two operands, so a query that holds both has a twin that holds one, and
/// refusing it in this order as in the other leaves its legality to the
/// query, not to the order of its conjuncts. An earlier conjunct that makes
/// a label is never the redundant one here: an atom that makes a label
/// matches no later atom's sites, and a comparison that makes one keeps the
/// outcome equal alone, which a later comparison of its operands keeps or
/// contradicts.
pub fn makes_earlier_redundant(body: &Body) -> Option<&'static str> {
    let (last, earlier) = body.conjuncts.split_last()?;
    match last {
        Conjunct::Atom(atom) => earlier.iter().find_map(|prior| match prior {
            Conjunct::Atom(prior) if matched_by(prior.value(), atom.value()) => Some("atom.implies_earlier"),
            _ => None,
        }),
        Conjunct::Not(Negated::Atom(atom)) => earlier.iter().find_map(|prior| match prior {
            Conjunct::Not(Negated::Atom(prior)) if matched_by(atom.value(), prior.value()) => Some("not.implies_earlier"),
            _ => None,
        }),
        Conjunct::Constraint(constraint) => earlier.iter().find_map(|prior| {
            let Conjunct::Constraint(prior) = prior else { return None };
            let (first, second) = pair_outcomes(prior, constraint)?;
            if first & second == 0 || first & !second == 0 {
                None
            } else if second & !first == 0 {
                Some("comparison.implies_earlier")
            } else {
                Some("comparison.merges")
            }
        }),
        _ => None,
    }
}

/// The rule by which the last conjunct of a flat decoder body reads the row
/// that an earlier atom of its relation reads, where it does: the two are
/// positive atoms whose sites hold the same values at each column of a key of
/// the relation, which `keys` gives. The relation has at most one row of each
/// value of a key, so the two atoms match one row, and one atom with the
/// sites of both reads it.
pub fn reads_an_earlier_row(body: &Body, keys: &dyn Fn(&RelationRef) -> Vec<Vec<ColumnName>>) -> Option<&'static str> {
    let (Conjunct::Atom(last), earlier) = body.conjuncts.split_last()? else { return None };
    let last = last.value();
    let later = held(last)?;
    let keys = keys(&last.relation);
    let at = |sites: &[(&ColumnName, Held, bool)], column: &ColumnName| sites.iter().find(|(c, _, _)| *c == column).map(|(_, value, _)| *value);
    earlier.iter().find_map(|prior| {
        let Conjunct::Atom(prior) = prior else { return None };
        if prior.value().relation != last.relation {
            return None;
        }
        let prior = held(prior.value())?;
        keys.iter()
            .any(|key| !key.is_empty() && key.iter().all(|column| at(&prior, column).is_some_and(|value| at(&later, column) == Some(value))))
            .then_some("atom.same_row")
    })
}

/// The rule by which the last conjunct of a flat decoder body makes an
/// earlier membership atom of it redundant, where it does: the last atom
/// reads, at a column whose type is at or below the membership's type, the
/// label that the membership atom makes, `binds` says that it can make that
/// label itself, and some order of the other conjuncts has the last atom make
/// the label before each conjunct that reads it
/// ([`last_can_make_before_uses`]). Each value at that column is then a
/// member, so the conjunction equals one with no membership atom, where the
/// label is made at that column. A membership atom that comes after such an
/// atom is valid by `membership.subtype`, so a query that holds both is
/// refused in each order.
pub fn makes_membership_redundant(
    body: &Body,
    column_type: &dyn Fn(&RelationRef, &ColumnName) -> Option<ValueType>,
    binds: &dyn Fn(&Atom, &ColumnName) -> bool,
) -> Option<&'static str> {
    let (last_conjunct, earlier) = body.conjuncts.split_last()?;
    let Conjunct::Atom(last) = last_conjunct else { return None };
    let last = last.value();
    if matches!(&last.relation, RelationRef::Lib(name) if membership_type(&name.0).is_some()) {
        return None;
    }
    let made_by_membership = |label: LabelId, ty: &ValueType| {
        earlier.iter().any(|prior| {
            let Conjunct::Atom(prior) = prior else { return false };
            let prior = prior.value();
            let RelationRef::Lib(name) = &prior.relation else { return false };
            let Some(tested) = membership_type(&name.0) else { return false };
            let makes = match &prior.sites[..] {
                [only] => matches!(&only.value.args[..], [SiteArg::Label(LabelUse::Fresh(made))] if *made == label),
                _ => false,
            };
            makes && ty.is_below(&tested)
        })
    };
    last.sites.iter().find_map(|site| {
        let [SiteArg::Label(LabelUse::Join(label))] = &site.value.args[..] else { return None };
        let ty = column_type(&last.relation, &site.column)?;
        let ty = if matches!(ty, ValueType::Pose(_)) { ValueType::D4 } else { ty };
        (made_by_membership(*label, &ty) && binds(last, &site.column) && last_can_make_before_uses(earlier, last_conjunct, *label)).then_some("membership.implied_later")
    })
}

/// Whether `conjunct` is a membership atom that makes `label`: a positive atom
/// of a membership relation whose one site makes `label`.
fn is_membership_maker(conjunct: &Conjunct, label: LabelId) -> bool {
    let Conjunct::Atom(atom) = conjunct else { return false };
    let atom = atom.value();
    let RelationRef::Lib(name) = &atom.relation else { return false };
    membership_type(&name.0).is_some()
        && match &atom.sites[..] {
            [only] => matches!(&only.value.args[..], [SiteArg::Label(LabelUse::Fresh(made))] if *made == label),
            _ => false,
        }
}

/// The labels that `conjunct` makes with `*` or `^`, then the labels it joins,
/// at any depth.
fn label_flow(conjunct: &Conjunct) -> (Vec<LabelId>, Vec<LabelId>) {
    let body = Body { conjuncts: vec![conjunct.clone()].into() };
    let (mut makes, mut joins) = (Vec::new(), Vec::new());
    crate::safety::each_label_use(&body, &mut |use_| match use_ {
        LabelUse::Fresh(label) | LabelUse::Key(label) => makes.push(label),
        LabelUse::Join(label) => joins.push(label),
        LabelUse::Zero => {}
    });
    (makes, joins)
}

/// Whether some order of the conjuncts of `earlier` and `last`, less the
/// membership atom that makes `label`, has `last` make `label` before every
/// conjunct that reads it, with each other label made before it is read.
///
/// The written order makes each other label before its readers. A new order
/// puts `last` before each reader of `label`, so it needs `last` to follow
/// the makers of the labels it joins, and a reader of `label` that `last`
/// depends on, through those makers, rules every such order out. A conjunct
/// that reads `label` between the membership atom and `last`, such as a `NOT`
/// or an atom that cannot make it, moves after `last` where `last` does not
/// depend on it.
fn last_can_make_before_uses(earlier: &[Conjunct], last: &Conjunct, label: LabelId) -> bool {
    let mut flows: Vec<(Vec<LabelId>, Vec<LabelId>)> =
        earlier.iter().filter(|conjunct| !is_membership_maker(conjunct, label)).map(label_flow).collect();
    flows.push(label_flow(last));
    let at = flows.len() - 1;
    let mut depends = vec![false; flows.len()];
    let mut pending = vec![at];
    while let Some(item) = pending.pop() {
        for read in flows[item].1.iter().filter(|read| **read != label) {
            for (maker, flow) in flows.iter().enumerate() {
                if maker != item && !depends[maker] && flow.0.contains(read) {
                    depends[maker] = true;
                    pending.push(maker);
                }
            }
        }
    }
    !flows.iter().enumerate().any(|(index, flow)| index != at && depends[index] && flow.1.contains(&label))
}

/// The refusal message of the static prune's rule `rule`, for the rules whose
/// refusal names its rule.
pub fn rule_message(rule: &str) -> Option<&'static str> {
    Some(match rule {
        "atom.implied" => "static prune: an earlier atom of the relation matches each site of the completed atom",
        "not.contradicted" => "static prune: a positive atom matches each site of a `NOT` of its relation",
        "not.implied" => "static prune: an earlier `NOT` of the relation refuses each row the completed `NOT` refuses",
        "comparison.implied" => "static prune: an earlier comparison of the two operands implies the completed one",
        "comparison.contradicted" => "static prune: an earlier comparison of the two operands contradicts the completed one",
        "atom.implies_earlier" => "static prune: the completed atom matches each site of an earlier atom of its relation that makes no label",
        "not.implies_earlier" => "static prune: the completed `NOT` refuses each row an earlier `NOT` of its relation refuses",
        "comparison.implies_earlier" => "static prune: the completed comparison implies an earlier comparison of its two operands",
        "comparison.merges" => "static prune: two comparisons of the same two operands are one comparison",
        "membership.subtype" => "static prune: the column that makes the label holds only members of the membership's type",
        "membership.implied_later" => "static prune: the completed atom's column holds only members of the type that an earlier membership atom tests, and can make that atom's label",
        "atom.same_row" => "static prune: by a key of its relation, the completed atom reads the row an earlier atom of the relation reads",
        _ => return None,
    })
}

#[cfg(test)]
mod review_regressions {
    use super::*;

    fn atom(name: &str, sites: &[(&str, LabelUse)]) -> Conjunct {
        Conjunct::Atom(Node::new(Atom {
            relation: RelationRef::Lib(crate::registry::LibName(name.into())),
            sites: sites
                .iter()
                .map(|(column, label)| Site {
                    column: ColumnName::Written((*column).into()),
                    value: SiteValue {
                        args: vec![SiteArg::Label(*label)].into(),
                    },
                })
                .collect(),
        }))
    }

    #[test]
    fn nat_order_requires_reserved_zero_not_another_nat_label() {
        let binding = |_: LabelId| Some(ValueType::Nat);
        let first = ConstraintLabel {
            label: LabelId(0),
            fresh: false,
        };
        let other = Operand::Label(ConstraintLabel {
            label: LabelId(1),
            fresh: false,
        });
        for op in [ConstraintOp::Lt, ConstraintOp::Ge] {
            assert!(
                classify(
                    &Conjunct::Constraint(Constraint {
                        first,
                        op,
                        second: other
                    }),
                    &binding
                )
                .is_none()
            );
        }
        assert_eq!(
            classify(
                &Conjunct::Constraint(Constraint {
                    first,
                    op: ConstraintOp::Lt,
                    second: Operand::Zero
                }),
                &binding
            )
            .unwrap()
            .class,
            Class::Unsatisfiable
        );
        assert_eq!(
            classify(
                &Conjunct::Constraint(Constraint {
                    first,
                    op: ConstraintOp::Ge,
                    second: Operand::Zero
                }),
                &binding
            )
            .unwrap()
            .class,
            Class::Valid
        );
    }

    #[test]
    fn zero_output_is_not_redundant_if_direction_still_filters() {
        let a = atom(
            "edge_inset",
            &[
                ("D", LabelUse::Join(LabelId(0))),
                ("K", LabelUse::Zero),
                ("B", LabelUse::Fresh(LabelId(1))),
            ],
        );
        assert!(classify(&a, &|_| Some(ValueType::Dir8)).is_none());
        assert_eq!(
            classify(&a, &|_| Some(ValueType::Dir)).unwrap().class,
            Class::Constant
        );
    }

    #[test]
    fn key_alias_has_no_local_equality_operand() {
        let a = atom(
            "compose",
            &[
                ("A", LabelUse::Key(LabelId(0))),
                ("B", LabelUse::Zero),
                ("C", LabelUse::Fresh(LabelId(1))),
            ],
        );
        let found = classify(&a, &|_| Some(ValueType::Box)).unwrap();
        assert_eq!(found.class, Class::Alias);
        assert!(found.replacement.is_none());
    }

    #[test]
    fn identity_on_literal_zero_is_a_constant() {
        let a = atom(
            "compose",
            &[
                ("A", LabelUse::Zero),
                ("B", LabelUse::Zero),
                ("C", LabelUse::Fresh(LabelId(0))),
            ],
        );
        assert_eq!(classify(&a, &|_| None).unwrap().class, Class::Constant);
    }
}

