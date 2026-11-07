//! The type rules of a lib relation or relation macro: the types its
//! `Box` columns take at a site from the types of the labels at the site's
//! other columns, and from whether two of those labels stand in one grid.

use super::spellings::SAME_FRAME;
use super::*;
use crate::program::column_spelled;
use crate::types::{column_label, Meet};

/// A rule `(when (<condition> ...) (<column> <type>) ...)` of a `types`
/// form: it holds at a site where each column of `when` has a label whose
/// type stands at or under the column's type, and each pair of `same_frame`
/// has labels that stand in one grid; at a site where it holds, each column
/// of `gives` has the type given.
#[derive(Clone, Debug)]
pub struct TypeRule {
    /// The place of the rule's form, where a diagnostic on it stands.
    pub place: SourcePlace,
    pub when: Box<[(ColumnName, ValueType)]>,
    /// The condition `(same-frame <column> <column>)`: two distinct `Box`
    /// columns of the relation.
    pub same_frame: Box<[(ColumnName, ColumnName)]>,
    pub gives: Box<[(ColumnName, ValueType)]>,
}

impl TypeRule {
    /// Whether the rule holds where `column_type` gives the type of the label
    /// at each column, and `share_grid` tells whether the labels at two
    /// columns stand in one grid.
    pub(crate) fn holds(&self, column_type: &dyn Fn(&ColumnName) -> Option<ValueType>, share_grid: &dyn Fn(&ColumnName, &ColumnName) -> bool) -> bool {
        self.when.iter().all(|(column, ty)| column_type(column).is_some_and(|found| at_or_under(&found, ty))) && self.same_frame.iter().all(|(a, b)| share_grid(a, b))
    }
}

/// The meet of `types`, or `None` for none.
fn meet_all(types: impl IntoIterator<Item = ValueType>) -> Option<ValueType> {
    types.into_iter().reduce(|a, b| match a.meet(&b) {
        Meet::Type(met) => met,
        Meet::Empty => unreachable!("the registry reader refuses rules that give a column types with an empty meet"),
    })
}

/// The type that a column declared as `declared` has at a site of `atom`: the
/// meet of `declared` and of the type each rule of `rules` that gives the
/// column `column` and holds there gives it. `label_type` gives the type of
/// a label, and `share_grid` whether two labels stand in one grid. Both the
/// type check and the derivation of a macro's rules read a site's rules here.
pub fn ruled_type(
    declared: ValueType,
    rules: &[TypeRule],
    column: &ColumnName,
    atom: &Atom,
    label_type: &dyn Fn(LabelId) -> Option<ValueType>,
    share_grid: &dyn Fn(LabelId, LabelId) -> bool,
) -> ValueType {
    let column_type = |at: &ColumnName| column_label(atom, at).and_then(label_type);
    let share = |a: &ColumnName, b: &ColumnName| column_label(atom, a).zip(column_label(atom, b)).is_some_and(|(a, b)| share_grid(a, b));
    let held = rules.iter().filter(|rule| rule.holds(&column_type, &share));
    let given = held.flat_map(|rule| rule.gives.iter().filter(|(given, _)| given == column).map(|(_, ty)| ty.clone()));
    meet_all(std::iter::once(declared).chain(given)).expect("the declared type is one of the types met")
}

impl AlgebraRelation {
    /// Whether a rule of the relation gives the column `column` a type.
    pub fn is_ruled(&self, column: &ColumnName) -> bool {
        self.rules.iter().any(|rule| rule.gives.iter().any(|(given, _)| given == column))
    }

    /// Whether a rule of the relation with a `same-frame` condition gives the
    /// column `column` a type.
    pub fn is_framed(&self, column: &ColumnName) -> bool {
        self.rules.iter().any(|rule| !rule.same_frame.is_empty() && rule.gives.iter().any(|(given, _)| given == column))
    }
}

/// The types a condition column takes in the check of a rule set: the types
/// of a `Box` column that a rule tells apart.
const BOX_TYPES: [ValueType; 3] = [ValueType::Box, ValueType::Position, ValueType::Offset];

/// The diagnostics of the rules of the relation `name` with `columns`, one
/// at each rule that has a fault. A rule names columns of the relation of a
/// `Box` type, gives each at or under its declared type, and gives none that
/// it has a condition on. A `same-frame` condition names two distinct
/// columns, and a rule of a macro, where `grids` is false, has none, since a
/// macro's derivation sees no grids. Then no two rules that hold at one
/// assignment of `Box`, `Position` and `Offset` to the condition columns,
/// with each `same-frame` condition holding, give a column types whose meet
/// is empty.
pub(super) fn rule_diagnostics(name: &LibName, columns: &[Column], rules: &[TypeRule], grids: bool) -> Vec<crate::diagnostic::Diagnostic> {
    let mut diagnostics = Vec::new();
    let mut fault = |rule: &TypeRule, message: String| {
        diagnostics.push(crate::read::check_error(CheckId::Types, format!("a type rule of `{}` {message}", name.0), rule.place));
    };
    let declared = |column: &ColumnName| columns.iter().find(|own| own.name == *column).and_then(|own| own.ty.fixed()).filter(|ty| ty.is_box());
    let mut sound: Vec<&TypeRule> = Vec::new();
    for rule in rules {
        let mut faulted = false;
        let mut conditioned: Vec<&ColumnName> = Vec::new();
        for (column, ty) in rule.when.iter() {
            let ok = declared(column).is_some_and(|declared| ty.is_box() && at_or_under(ty, declared)) && !conditioned.contains(&column);
            if !ok {
                fault(rule, format!("conditions the column {:?}, which is no `Box` column of the relation that the type {ty:?} stands at or under, or conditions it twice", column_spelled(column)));
                faulted = true;
            }
            conditioned.push(column);
        }
        for (a, b) in rule.same_frame.iter() {
            let ok = grids && a != b && declared(a).is_some() && declared(b).is_some();
            if !ok {
                fault(
                    rule,
                    format!("conditions `{SAME_FRAME}` on the columns {:?} and {:?}, which are not two distinct `Box` columns of a lib relation (a macro's rule has no such condition)", column_spelled(a), column_spelled(b)),
                );
                faulted = true;
            }
            conditioned.extend([a, b]);
        }
        let mut given: Vec<&ColumnName> = Vec::new();
        for (column, ty) in rule.gives.iter() {
            let ok = declared(column).is_some_and(|declared| ty.is_box() && at_or_under(ty, declared)) && !conditioned.contains(&column) && !given.contains(&column);
            if !ok {
                fault(rule, format!("gives the column {:?} the type {ty:?}, which is not a type at or under the type that the relation declares for it, or the column has a condition of the rule or a second type", column_spelled(column)));
                faulted = true;
            }
            given.push(column);
        }
        if given.is_empty() {
            fault(rule, "gives no column a type".to_string());
            faulted = true;
        }
        if !faulted {
            sound.push(rule);
        }
    }
    diagnostics.extend(disagreements(name, &sound));
    diagnostics
}

/// A diagnostic at each rule of `rules` that gives a column, at an
/// assignment of `Box`, `Position` and `Offset` to the condition columns
/// where it and an earlier rule both hold, a type whose meet with the earlier
/// rule's is empty.
fn disagreements(name: &LibName, rules: &[&TypeRule]) -> Vec<crate::diagnostic::Diagnostic> {
    let mut conditioned: Vec<&ColumnName> = Vec::new();
    for rule in rules {
        for (column, _) in rule.when.iter() {
            if !conditioned.contains(&column) {
                conditioned.push(column);
            }
        }
    }
    let mut diagnostics = Vec::new();
    let assignments = BOX_TYPES.len().pow(conditioned.len() as u32);
    for number in 0..assignments {
        let mut rest = number;
        let mut types: Vec<(&ColumnName, &ValueType)> = Vec::new();
        for column in &conditioned {
            types.push((column, &BOX_TYPES[rest % BOX_TYPES.len()]));
            rest /= BOX_TYPES.len();
        }
        let column_type = |column: &ColumnName| types.iter().find(|(found, _)| *found == column).map(|(_, ty)| (*ty).clone());
        let holding: Vec<&&TypeRule> = rules.iter().filter(|rule| rule.holds(&column_type, &|_, _| true)).collect();
        for (at, rule) in holding.iter().enumerate() {
            for (column, ty) in rule.gives.iter() {
                let earlier = holding[..at].iter().flat_map(|other| other.gives.iter()).find(|(other, other_ty)| other == column && !ty.meets(other_ty));
                if let Some((_, other_ty)) = earlier {
                    let message = format!(
                        "a type rule of `{}` gives the column {:?} the type {ty:?}, and a rule that holds with it gives {other_ty:?}, whose meet is empty",
                        name.0,
                        column_spelled(column)
                    );
                    diagnostics.push(crate::read::check_error(CheckId::Types, message, rule.place));
                }
            }
        }
    }
    diagnostics
}
