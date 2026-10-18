//! The reader of the registry file's macro form,
//! `(macro <name> (columns ...) <body>)`, with the labels of its body that
//! its columns stand for.

use super::reader::{headed, BodyInFile, FileReader, WrittenMacro, LabelColumns, COLUMNS};
use super::*;

impl FileReader {
    /// `(macro <name> (columns ...) <body>)`, after its head.
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

    /// Each `(<Column> <Label>)` of `items`, the column's name and the label
    /// of `labels` it stands for. `what` names the form whose columns they
    /// are.
    fn label_columns(&mut self, items: &[SExpr], labels: &crate::read::LabelNames, what: &str, place: SourcePlace) -> Option<LabelColumns> {
        let mut columns = Vec::new();
        for item in items {
            let SExpr::List { items: pair, .. } = item else {
                return self.refuse(format!("a column of {what} is a list of its name and its label"), item.place());
            };
            let [column, label] = &pair[..] else {
                return self.refuse(format!("a column of {what} is a list of its name and its label"), item.place());
            };
            let column = self.symbol(Some(column), "the column's name", place)?;
            let label = self.symbol(Some(label), "the column's label", place)?;
            let label = self.label_of(labels, label, &format!("the column `{column}` of {what}"), place)?;
            columns.push((ColumnName::Written(column.into()), label));
        }
        Some(columns.into())
    }

    fn relation_macro(&mut self, name: LibName, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let written = headed(&rest[1], COLUMNS).expect("the form's `columns` form");
        let (definition, labels) = self.read(read_body(&rest[2..]))?;
        let columns = self.label_columns(written, &labels, &format!("the macro `{}`", name.0), place)?;
        if self.declare(&name, place) {
            self.bodies.push(BodyInFile { body: definition.clone(), place });
            self.relation_macros.push(WrittenMacro { name, place, columns, definition });
        }
        Some(())
    }
}
