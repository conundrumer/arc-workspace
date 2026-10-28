//! The declaration of each relation macro of the registry file and each
//! proposer written in arclog, from the columns and modes of the file's
//! other names, once every form is read.

use super::reader::FileReader;
use super::*;

impl FileReader {
    /// Gives each relation macro its declaration, and each proposer written
    /// in arclog its columns, with their types and no modes, as
    /// [`macro_column_types`] derives them from the columns of the other
    /// forms' names and of the fact relations, and the modes of the
    /// `relation` forms. A proposer is read as a relation macro whose
    /// definition is its clause.
    pub(super) fn declare_macros(&mut self) {
        let mut lib: StableHashMap<LibName, Box<[Column]>> = StableHashMap::default();
        let mut modes: StableHashMap<LibName, Box<[Mode]>> = StableHashMap::default();
        for (name, entry) in &self.entries {
            match entry {
                LibEntry::Relation(relation) => {
                    lib.insert(name.clone(), relation.columns.clone());
                    modes.insert(name.clone(), relation.modes.clone());
                }
                LibEntry::Proposer(proposer) => {
                    lib.insert(name.clone(), proposer.columns.clone());
                }
                LibEntry::Component(_) | LibEntry::Macro(_) => {}
            }
        }
        let macros: Vec<RelationMacro<'_>> = self
            .written_relations()
            .map(|m| RelationMacro { name: &m.name, place: m.place, columns: &m.columns, definition: m.definition.value() })
            .collect();
        let declarations = macro_column_types(&macros, &lib, &modes, &self.facts);
        match declarations {
            Ok(mut declarations) => {
                for m in std::mem::take(&mut self.relation_macros) {
                    let mut relation = declarations.relations.remove(&m.name).expect("each relation macro takes a declaration");
                    let what = format!("the macro `{}`", m.name.0);
                    relation.frames = self.relation_frames(&m.frames, &relation.columns, &what).unwrap_or_default();
                    let labels = m.columns.iter().map(|column| column.label).collect();
                    self.entries.insert(m.name, LibEntry::Macro(Macro::Relation { relation, labels, definition: m.definition }));
                }
                for p in std::mem::take(&mut self.proposer_clauses) {
                    let relation = declarations.relations.remove(&p.name).expect("each proposer written in arclog takes a declaration");
                    let kind = ProposerKind::Arclog { body: p.definition };
                    self.entries.insert(p.name, LibEntry::Proposer(Proposer { columns: relation.columns, kind }));
                }
            }
            Err(diagnostics) => self.diagnostics.extend(diagnostics),
        }
    }
}
