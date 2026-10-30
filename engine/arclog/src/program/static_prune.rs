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
