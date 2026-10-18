//! The reader of the proposers file, `engine/lib/proposers.arclog`, which
//! gives each proposer written in arclog its clause.

use super::reader::{headed, BodyInFile, FileReader, PROPOSER};
use crate::read::LabelNames;
use super::*;

impl FileReader {
    /// Reads the forms of the proposers file, and gives each
    /// `(proposer <name> arclog (columns ...))` form its clause, with the
    /// columns the form names, each a label the clause keeps.
    pub(super) fn proposer_clauses(&mut self, exprs: &[SExpr]) {
        let mut clauses: Vec<(LibName, SourcePlace, Node<Body>, LabelNames)> = Vec::new();
        for expr in exprs {
            let place = expr.place();
            let Some(rest) = headed(expr, PROPOSER) else {
                self.refuse::<()>("a form of the proposers file is a `(proposer <Name> <atom> ...)` form", place);
                continue;
            };
            let Some(name) = self.symbol(rest.first(), "the proposer's name", place) else { continue };
            let name = LibName(name.into());
            let Some((body, kept)) = self.read(read_body(&rest[1..])) else { continue };
            if clauses.iter().any(|(n, ..)| *n == name) {
                self.fault(CheckId::Scope, format!("the proposer `{}` has two clauses", name.0), place);
                continue;
            }
            self.bodies.push(BodyInFile { body: body.clone(), place });
            clauses.push((name, place, body, kept));
        }
        for proposer in std::mem::take(&mut self.arclog_proposers) {
            let Some(index) = clauses.iter().position(|(n, ..)| *n == proposer.name) else {
                let message = format!("the proposer `{}` has no clause in the proposers file", proposer.name.0);
                self.fault(CheckId::Scope, message, proposer.place);
                continue;
            };
            let (name, _, body, kept) = clauses.remove(index);
            let what = |label: &str| format!("the column `{label}` of the proposer `{}`", name.0);
            let columns: Vec<Option<ColumnName>> = proposer
                .columns
                .iter()
                .map(|label| self.label_of(&kept, label, &what(label), proposer.place).map(|_| ColumnName::Written(label.clone())))
                .collect();
            if let Some(columns) = columns.into_iter().collect::<Option<Box<[ColumnName]>>>() {
                self.entries.insert(name, LibEntry::Proposer(Proposer::Arclog { columns, body }));
            }
        }
        for (name, place, ..) in clauses {
            self.fault(CheckId::Scope, format!("the clause of `{}` stands for no `(proposer {} arclog ...)` form", name.0, name.0), place);
        }
    }
}
