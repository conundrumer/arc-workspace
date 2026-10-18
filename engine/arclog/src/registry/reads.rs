//! The check of the reads of the bodies of the two lib files: each atom
//! reads a name that a form declares, at columns that name declares.

use super::column_types::column_display;
use super::reader::FileReader;
use super::*;

impl FileReader {
    /// Gives a diagnostic at each atom of a body of either file that reads a
    /// name no form declares, or a column its name does not declare.
    pub(super) fn check_reads(&mut self) {
        let mut faults = Vec::new();
        for body in &self.bodies {
            each_atom(body.body.value(), &mut |atom| {
                let relation = crate::write::relation_ref(&atom.relation);
                let columns = match self.columns_of(&atom.relation) {
                    Ok(columns) => columns,
                    Err(fault) => {
                        faults.push((CheckId::Scope, format!("an atom of `{relation}` {fault}"), body.place));
                        return;
                    }
                };
                for site in atom.sites.iter().filter(|site| !columns.contains(&site.column)) {
                    let message = format!("an atom of `{relation}` has a site at `{}`, which is no column of `{relation}`", column_display(&site.column));
                    faults.push((CheckId::SiteColumns, message, body.place));
                }
            });
        }
        for (check, message, place) in faults {
            self.fault(check, message, place);
        }
    }

    /// The columns of the relation that `relation` names, read from a body
    /// of either file, or the fault of a read of a name no form declares.
    fn columns_of(&self, relation: &RelationRef) -> Result<Vec<ColumnName>, String> {
        let names = |columns: &[Column]| columns.iter().map(|c| c.name.clone()).collect();
        let undeclared = || "reads a name that no form of the registry file declares".to_string();
        match relation {
            RelationRef::Fact(fact) => self.facts.get(fact).map(|c| names(c)).ok_or_else(|| "reads a fact relation that no `fact` form declares".to_string()),
            RelationRef::Lib(name) => {
                if let Some(m) = self.written_relations().find(|m| m.name == *name) {
                    return Ok(m.columns.iter().map(|(c, _)| c.clone()).collect());
                }
                match self.entries.get(name) {
                    Some(LibEntry::Relation(relation)) => Ok(names(&relation.columns)),
                    Some(LibEntry::Proposer(proposer)) => Ok(names(&proposer.columns)),
                    Some(LibEntry::Macro(Macro::Relation { relation, .. })) => Ok(names(&relation.columns)),
                    Some(LibEntry::Component(_)) => Err("reads a component, which an `INIT` form instantiates and no atom reads".to_string()),
                    None => Err(undeclared()),
                }
            }
            RelationRef::DefinedPort(_) | RelationRef::Declared(_) | RelationRef::Output(_) => Err(undeclared()),
        }
    }
}
