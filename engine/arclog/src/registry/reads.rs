//! The check of the reads of the bodies of the two lib files: each atom
//! reads a name that a form declares, at columns that name declares.

use super::column_types::column_display;
use super::reader::{FileReader, WrittenCell};
use super::*;

impl FileReader {
    /// Gives a diagnostic at each atom of a body of either file that reads a
    /// name no form declares, or a column its name does not declare.
    pub(super) fn check_reads(&mut self) {
        let mut faults = Vec::new();
        for body in &self.bodies {
            let cell = body.cell.map(|cell| &self.cells[cell]);
            each_conjunct(body.body.value(), &mut |conjunct| {
                let (Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom))) = conjunct else { return };
                let atom = atom.value();
                let relation = crate::write::relation_ref(&atom.relation);
                let columns = match self.columns_of(&atom.relation, cell) {
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
    /// of either file, within the cell instance `cell` where it stands in
    /// one, or the fault of a read of a name no form declares.
    fn columns_of(&self, relation: &RelationRef, cell: Option<&WrittenCell>) -> Result<Vec<ColumnName>, String> {
        let names = |columns: &[Column]| columns.iter().map(|c| c.name.clone()).collect();
        match relation {
            RelationRef::Fact(fact) => self.facts.get(fact).map(|c| names(c)).ok_or_else(|| "reads a fact relation that no `fact` form declares".to_string()),
            RelationRef::Lib(name) => {
                if let Some(m) = self.relation_macros.iter().find(|m| m.name == *name) {
                    return Ok(m.columns.iter().map(|(c, _)| c.clone()).collect());
                }
                let component = "reads a component, which an `INIT` form instantiates and no atom reads".to_string();
                if self.cells.iter().any(|cell| cell.name == *name) {
                    return Err(component);
                }
                match self.entries.get(name) {
                    Some(LibEntry::Relation(relation)) => Ok(names(&relation.columns)),
                    Some(LibEntry::Proposer(Proposer::Native { columns })) => Ok(names(columns)),
                    Some(LibEntry::Proposer(Proposer::Arclog { columns, .. })) => Ok(columns.to_vec()),
                    Some(LibEntry::Macro(Macro::Relation { relation, .. })) => Ok(names(&relation.columns)),
                    Some(LibEntry::Component(_) | LibEntry::Macro(Macro::CellInstance { .. })) => Err(component),
                    None => Err("reads a name that no form of the registry file declares".to_string()),
                }
            }
            RelationRef::DefaultRows { .. } => Err("reads the default rows of an input, which only an expansion reads".to_string()),
            RelationRef::DefinedPort(port) => {
                let input = cell.and_then(|cell| cell.inputs.iter().find(|input| input.port.name == *port));
                input.map(|input| names(&input.port.columns)).ok_or_else(|| "reads no input of its cell instance".to_string())
            }
            RelationRef::Declared(rule) => {
                let rule = cell.and_then(|cell| cell.rules.iter().find(|written| written.name == *rule));
                rule.map(|rule| rule.columns.iter().map(|(column, _)| column.clone()).collect()).ok_or_else(|| "reads no `RULE` form of its cell instance".to_string())
            }
            RelationRef::Output(output) => {
                let columns = match (&output.of, &output.path[..], cell.and_then(|cell| cell.init())) {
                    (OutputOwner::Instance(instance), [OutputStep::Port(port)], Some(init)) if *instance == init.name => {
                        self.output_columns(&init.component, port)
                    }
                    _ => None,
                };
                columns.ok_or_else(|| "reads no output of its cell instance's `INIT` form".to_string())
            }
        }
    }

    /// The columns of the output `port` of the component `name` declares, a
    /// component's or a cell instance's.
    fn output_columns(&self, name: &LibName, port: &PortName) -> Option<Vec<ColumnName>> {
        if let Some(cell) = self.cells.iter().find(|cell| cell.name == *name) {
            let (_, columns, _) = cell.outputs.iter().find(|(p, _, _)| p == port)?;
            return Some(columns.iter().map(|(column, _)| column.clone()).collect());
        }
        match self.entries.get(name)? {
            LibEntry::Component(component) => Some(component.outputs.iter().find(|output| output.name == *port)?.columns.iter().map(|c| c.name.clone()).collect()),
            LibEntry::Relation(_) | LibEntry::Proposer(_) | LibEntry::Macro(_) => None,
        }
    }
}
