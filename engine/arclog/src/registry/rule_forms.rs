//! The reader of the `types` form of a `relation` form and of a `macro`
//! form of the registry file: its rules, `(when (<condition> ...)
//! (<Column> <type>) ...)`, each condition `(<Column> <type>)` or
//! `(same-frame <Column> <Column>)`.

use super::reader::FileReader;
use super::spellings::*;
use super::*;

impl FileReader {
    /// The rules that `items`, the items of a `(types ...)` form, write.
    pub(super) fn type_rules(&mut self, items: &[SExpr]) -> Option<Box<[TypeRule]>> {
        let rules: Option<Vec<TypeRule>> = items.iter().map(|item| self.type_rule(item)).collect();
        rules.map(Into::into)
    }

    /// The rule that `expr`, a `(when ...)` form, writes.
    fn type_rule(&mut self, expr: &SExpr) -> Option<TypeRule> {
        let place = expr.place();
        let Some(rest) = headed(expr, WHEN) else {
            return self.refuse(format!("a rule of a `{TYPES}` form is a `({WHEN} ...)` form"), place);
        };
        let [SExpr::List { items: conditions, .. }, results @ ..] = rest else {
            return self.refuse(format!("a `{WHEN}` rule lists its conditions, `(<condition> ...)`, first"), place);
        };
        let mut when = Vec::new();
        let mut same_frame = Vec::new();
        for condition in conditions.iter() {
            match headed(condition, SAME_FRAME) {
                Some(columns) => same_frame.push(self.same_frame_columns(columns, condition.place())?),
                None => when.push(self.typed_column(condition)?),
            }
        }
        let gives: Option<Vec<_>> = results.iter().map(|result| self.typed_column(result)).collect();
        Some(TypeRule { place, when: when.into(), same_frame: same_frame.into(), gives: gives?.into() })
    }

    /// The columns that `columns`, the items after `same-frame` of a
    /// `(same-frame <Column> <Column>)` condition at `place`, write.
    fn same_frame_columns(&mut self, columns: &[SExpr], place: SourcePlace) -> Option<(ColumnName, ColumnName)> {
        let [a, b] = columns else {
            return self.refuse(format!("a `{SAME_FRAME}` condition names two columns"), place);
        };
        let a = self.symbol(Some(a), "the column's name", place)?;
        let b = self.symbol(Some(b), "the column's name", place)?;
        Some((ColumnName::Written(a.into()), ColumnName::Written(b.into())))
    }

    /// The column and the type that `expr`, `(<Column> <type>)`, writes.
    fn typed_column(&mut self, expr: &SExpr) -> Option<(ColumnName, ValueType)> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("a rule's column is a list of its name and its type", expr.place());
        };
        let [name, ty] = &items[..] else {
            return self.refuse("a rule's column is a list of its name and its type", *place);
        };
        let name = self.symbol(Some(name), "the column's name", *place)?;
        Some((ColumnName::Written(name.into()), self.value_type(ty, "a rule's type")?))
    }

    /// Gives a diagnostic at each fault of the rules of a `relation` form, as
    /// [`rule_diagnostics`] gives them, and drops the rules of a relation that
    /// has one, so that [`FileReader::declare_macros`] reads no faulty rule.
    /// The rules of a macro are checked with its derivation.
    pub(super) fn check_rules(&mut self) {
        let mut ruled: Vec<&LibName> = self.entries.iter().filter(|(_, entry)| matches!(entry, LibEntry::Relation(relation) if !relation.rules.is_empty())).map(|(name, _)| name).collect();
        ruled.sort_by(|a, b| a.0.cmp(&b.0));
        let mut faults = Vec::new();
        let mut faulty = Vec::new();
        for name in ruled {
            let Some(LibEntry::Relation(relation)) = self.entries.get(name) else { continue };
            let found = rule_diagnostics(name, &relation.columns, &relation.rules, true);
            if !found.is_empty() {
                faulty.push(name.clone());
                faults.extend(found);
            }
        }
        self.diagnostics.extend(faults);
        for name in faulty {
            if let Some(LibEntry::Relation(relation)) = self.entries.get_mut(&name) {
                relation.rules = Box::default();
            }
        }
    }
}
