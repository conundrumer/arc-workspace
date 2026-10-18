//! The reader of the proposers file, `engine/lib/proposers.arclog`, which
//! gives each proposer written in arclog its clause.

use super::reader::{headed, BodyInFile, FileReader, PROPOSER};
use super::*;

impl FileReader {
    /// Reads the forms of the proposers file, and gives each
    /// `(proposer <name> arclog)` form its clause.
    pub(super) fn proposer_clauses(&mut self, exprs: &[SExpr]) {
        let mut clauses: Vec<(LibName, SourcePlace, Proposer)> = Vec::new();
        for expr in exprs {
            let place = expr.place();
            let Some(rest) = headed(expr, PROPOSER) else {
                self.refuse::<()>("a form of the proposers file is a `(proposer <Name> <atom> ...)` form", place);
                continue;
            };
            let Some(name) = self.symbol(rest.first(), "the proposer's name", place) else { continue };
            let name = LibName(name.into());
            let Some((body, kept)) = self.read(read_body(&rest[1..], None)) else { continue };
            if clauses.iter().any(|(n, _, _)| *n == name) {
                self.fault(CheckId::Scope, format!("the proposer `{}` has two clauses", name.0), place);
                continue;
            }
            let columns = kept.iter().map(|(n, _)| ColumnName::Written(n.clone())).collect();
            self.bodies.push(BodyInFile { body: body.clone(), place, cell: None });
            clauses.push((name, place, Proposer::Arclog { columns, body }));
        }
        for (name, place) in std::mem::take(&mut self.arclog_proposers) {
            match clauses.iter().position(|(n, _, _)| *n == name) {
                Some(index) => {
                    let (name, _, proposer) = clauses.remove(index);
                    self.entries.insert(name, LibEntry::Proposer(proposer));
                }
                None => self.fault(CheckId::Scope, format!("the proposer `{}` has no clause in the proposers file", name.0), place),
            }
        }
        for (name, place, _) in clauses {
            self.fault(CheckId::Scope, format!("the clause of `{}` stands for no `(proposer {} arclog)` form", name.0, name.0), place);
        }
    }
}
