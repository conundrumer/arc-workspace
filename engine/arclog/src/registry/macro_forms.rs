//! The reader of the registry file's macro form,
//! `(macro <name> (columns ...) [(modes ...)] [(frames ...)] [(types ...)] <body>)`, with the labels of
//! its body that its columns stand for.

use super::reader::FileReader;
use super::records::{BodyInFile, LabelColumns, WrittenRelation};
use super::spellings::{headed, COLUMNS, FRAMES, MODES, TYPES};
use super::*;

impl FileReader {
    /// `(macro <name> (columns ...) [(modes ...)] [(frames ...)] [(types ...)] <body>)`, after its head.
    pub(super) fn macro_form(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the macro's name", place)?.into());
        match rest.get(1).and_then(head_of) {
            Some(COLUMNS) => self.relation_macro(name, rest, place),
            _ => self.refuse(format!("a macro's name stands before its `({COLUMNS} ...)` form"), place),
        }
    }

    /// The label of `labels` named `name`, the first that stands, or a fault
    /// that `what` stands for no label the body keeps.
    pub(super) fn label_of(&mut self, labels: &crate::read::LabelNames, name: &str, what: &str, place: SourcePlace) -> Option<LabelId> {
        match labels.iter().find(|(n, _)| &**n == name) {
            Some((_, label)) => Some(*label),
            None => {
                self.fault(CheckId::Scope, format!("{what} stands for the label `{name}`, which its body does not keep"), place);
                None
            }
        }
    }

    /// Each `(<Column> <Label> <type>)` of `items`, the column's name, the
    /// label of `labels` it stands for and the type it declares, each column
    /// named once. `what` names the form whose columns they are.
    fn label_columns(&mut self, items: &[SExpr], labels: &crate::read::LabelNames, what: &str, place: SourcePlace) -> Option<LabelColumns> {
        let mut columns = Vec::new();
        let mut names: Vec<&str> = Vec::new();
        for item in items {
            let SExpr::List { items: pair, .. } = item else {
                return self.refuse(format!("a column of {what} is a list of its name, its label and its type"), item.place());
            };
            let [column, label, declared] = &pair[..] else {
                return self.refuse(format!("a column of {what} is a list of its name, its label and its type"), item.place());
            };
            let column = self.symbol(Some(column), "the column's name", place)?;
            let label = self.symbol(Some(label), "the column's label", place)?;
            let label = self.label_of(labels, label, &format!("the column `{column}` of {what}"), place)?;
            let declared = Some(self.value_type(declared, "a declared type")?);
            if !self.named_once(names.iter().copied(), column, what, item.place()) {
                continue;
            }
            names.push(column);
            columns.push(LabelColumn { name: ColumnName::Written(column.into()), label, declared });
        }
        Some(columns.into())
    }

    fn relation_macro(&mut self, name: LibName, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let written = headed(&rest[1], COLUMNS).expect("the form's `columns` form");
        let (modes, rest) = match rest.get(2).filter(|expr| headed(expr, MODES).is_some()) {
            Some(expr) => (Some(expr), &rest[3..]),
            None => (None, &rest[2..]),
        };
        let (frames, rest) = match rest.first().and_then(|expr| headed(expr, FRAMES)) {
            Some(frames) => (frames, &rest[1..]),
            None => (&[][..], rest),
        };
        let (rules, body) = match rest.first().and_then(|expr| headed(expr, TYPES)) {
            Some(items) => (self.type_rules(items)?, &rest[1..]),
            None => (Box::default(), rest),
        };
        let (definition, labels) = self.read(read_body(body))?;
        let columns = self.label_columns(written, &labels, &format!("the macro `{}`", name.0), place)?;
        let modes = match modes {
            Some(expr) => {
                let names: Vec<ColumnName> = columns.iter().map(|column| column.name.clone()).collect();
                self.modes(expr, &names, place)?
            }
            None => Box::default(),
        };
        if self.declare(&name, place) {
            self.bodies.push(BodyInFile { body: definition.clone(), place });
            self.relation_macros.push(WrittenRelation { name, place, columns, modes: Some(modes), definition, frames: frames.into(), rules });
        }
        Some(())
    }
}
