//! The declaration of each relation macro of the registry file, from the
//! columns and modes of the file's other names, once every form is read.

use super::reader::FileReader;
use super::*;

impl FileReader {
    /// Gives each relation macro its declaration, as [`macro_column_types`]
    /// derives it from the columns of the other forms' names and the modes
    /// of the `relation` forms.
    pub(super) fn declare_macros(&mut self) {
        let mut lib: StableHashMap<LibName, Box<[Column]>> = StableHashMap::default();
        let mut modes: StableHashMap<LibName, Box<[Mode]>> = StableHashMap::default();
        for (name, entry) in &self.entries {
            match entry {
                LibEntry::Relation(relation) => {
                    lib.insert(name.clone(), relation.columns.clone());
                    modes.insert(name.clone(), relation.modes.clone());
                }
                LibEntry::Proposer(Proposer::Native { columns }) => {
                    lib.insert(name.clone(), columns.clone());
                }
                LibEntry::Component(_) | LibEntry::Proposer(Proposer::Arclog { .. }) | LibEntry::Macro(_) => {}
            }
        }
        let macros: Vec<RelationMacro<'_>> = self
            .relation_macros
            .iter()
            .map(|m| RelationMacro { name: &m.name, place: m.place, columns: &m.columns, definition: m.definition.value() })
            .collect();
        let declarations = macro_column_types(&macros, &lib, &modes);
        match declarations {
            Ok(mut declarations) => {
                for m in std::mem::take(&mut self.relation_macros) {
                    let relation = declarations.relations.remove(&m.name).expect("each relation macro takes a declaration");
                    let labels = m.columns.iter().map(|(_, label)| *label).collect();
                    self.entries.insert(m.name, LibEntry::Macro(Macro::Relation { relation, labels, definition: m.definition }));
                }
            }
            Err(diagnostics) => self.diagnostics.extend(diagnostics),
        }
    }
}
