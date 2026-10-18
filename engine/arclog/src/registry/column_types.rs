//! The derivation of a macro's column types from its definition: a
//! relation macro's columns with their modes, and a cell instance's output
//! columns.

use super::cell_types::{cell_ports, CellMacro};
use super::*;

/// A relation macro of the file, as [`macro_column_types`] reads it.
#[derive(Clone, Copy, Debug)]
pub struct RelationMacro<'a> {
    pub name: &'a LibName,
    /// The place of the macro's form, where a diagnostic on it stands.
    pub place: SourcePlace,
    /// Each column's name and the label of the definition it stands for, in
    /// the order of the macro's columns.
    pub columns: &'a [(ColumnName, LabelId)],
    /// The definition, as [`crate::read::read_body`] gives it.
    pub definition: &'a Body,
}

/// The declarations of the macros of the file that
/// [`macro_column_types`] gives: each relation macro's, and each cell
/// instance's output ports.
#[derive(Clone, Debug)]
pub struct MacroDeclarations {
    pub relations: StableHashMap<LibName, AlgebraRelation>,
    /// Each cell instance's outputs, in the order of its `output` forms,
    /// each column with its type.
    pub cells: StableHashMap<LibName, Box<[Port]>>,
}

/// The declaration of each relation macro of `macros`, its columns in order
/// with their types and its modes, and the output ports of each cell
/// instance of `cells` with their column types, or a diagnostic at a
/// macro's form for each fault.
///
/// The type of a relation macro's column is the type that [`label_type`]
/// gives its label over the definition. A site has the column's type: a
/// column of a lib name that `lib` declares, where the type is fixed or
/// `(pose-or <type>)`, or a column of another macro of `macros`, of the type
/// this gives it. Any other site gives no type.
///
/// The modes are the minimal sets of the columns, other than an orientation
/// type's, whose labels, taken as grounded, let [`grounded_labels`] ground
/// every label of the definition. An atom of a lib relation takes the modes
/// that `modes` gives it, and an atom of another macro of `macros` the modes
/// this gives it. Where the empty set grounds the definition, the macro has
/// no mode, as a relation over a finite domain has none.
///
/// The type of a cell instance's output column is the type its `output`
/// body gives the column's label, by the sites a relation macro's label
/// takes, with these besides. A site on the cell instance's own input takes
/// the type that input's column declares, a type parameter of the cell
/// instance included. A site on an output of the `INIT` form's instance
/// takes the type of that output's column in the component the form
/// instantiates, a component of `components` or another cell instance of
/// `cells`, with each type parameter of that component bound as the form
/// binds it (`docs/arclog/arclog.md#instance`): to the type of a label, or
/// to a record with a field per site or per `^` label, whose fields a site
/// on that column reads by name. A site on a `RULE` form takes the type of
/// that form's column, the type its body gives the column's label. The
/// `INIT` form and the `RULE` forms are typed in an order of their reads of
/// one another, and a site that reads a form whose typing reads the form
/// that holds the site gives no type. A label whose sites give one type
/// parameter of the cell instance, and no fixed type, takes that parameter;
/// a label whose sites give no parameter takes the meet and join of their
/// types, as a relation macro's does.
///
/// `lib` holds the columns of each lib name that a form other than a
/// relation macro declares, and `modes` the modes of each `relation` form,
/// none for a form with no `modes` form. The macros are read in an order of
/// their reads of one another, so the order of `macros` and of `cells`
/// gives the order of the diagnostics alone. A fault is a cycle of macros
/// that read one another, given at each macro of the cycle; a column whose
/// label's sites have an empty meet, or whose branches give types with no
/// join; a column whose label stands at no site that gives a type; or a
/// definition that no set of the columns grounds. A macro that reads a
/// macro with a fault takes no declaration, and gives no diagnostic of its
/// own for it. A cell instance has the faults of a relation macro's labels
/// at each column of its outputs and its `RULE` forms, and these besides: a
/// type parameter of the instantiated component that the `INIT` form binds
/// to no type, a site that names a field its record does not have, and a
/// label whose sites give a type parameter of the cell instance beside
/// another parameter or a fixed type. Where a relation macro has a fault,
/// the cell instances are not read.
pub fn macro_column_types(
    macros: &[RelationMacro<'_>],
    cells: &[CellMacro<'_>],
    lib: &StableHashMap<LibName, Box<[Column]>>,
    modes: &StableHashMap<LibName, Box<[Mode]>>,
    components: &StableHashMap<LibName, Component>,
) -> Result<MacroDeclarations, Vec<crate::diagnostic::Diagnostic>> {
    let mut derivation = MacroDerivation {
        macros,
        lib,
        modes,
        index: macros.iter().enumerate().map(|(i, m)| (m.name.clone(), i)).collect(),
        states: vec![MacroState::Unread; macros.len()],
        stack: Vec::new(),
        diagnostics: Vec::new(),
    };
    for i in 0..macros.len() {
        derivation.read(i);
    }
    if !derivation.diagnostics.is_empty() {
        return Err(derivation.diagnostics);
    }
    let mut diagnostics = Vec::new();
    let cells = cell_ports(&derivation, cells, components, &mut diagnostics);
    if !diagnostics.is_empty() {
        return Err(diagnostics);
    }
    let relations = derivation.states.iter().zip(macros).map(|(state, m)| match state {
        MacroState::Declared(relation) => (m.name.clone(), relation.clone()),
        _ => unreachable!("a macro with no declaration gives a diagnostic"),
    });
    Ok(MacroDeclarations { relations: relations.collect(), cells })
}

/// Where [`macro_column_types`] stands in its read of one macro.
#[derive(Clone, Debug)]
enum MacroState {
    Unread,
    /// Its reads of other macros are being read, so a read of it now closes
    /// a cycle.
    Reading,
    /// Its declaration, each column of a fixed type.
    Declared(AlgebraRelation),
    /// It has a fault, or reads a macro with one.
    Faulted,
}

pub(super) struct MacroDerivation<'a, 'b> {
    macros: &'a [RelationMacro<'b>],
    lib: &'a StableHashMap<LibName, Box<[Column]>>,
    modes: &'a StableHashMap<LibName, Box<[Mode]>>,
    index: StableHashMap<LibName, usize>,
    states: Vec<MacroState>,
    /// The macros being read, each reading the next.
    stack: Vec<usize>,
    diagnostics: Vec<crate::diagnostic::Diagnostic>,
}

impl MacroDerivation<'_, '_> {
    /// Reads macro `i` after each macro it reads, and sets its state.
    fn read(&mut self, i: usize) {
        match self.states[i] {
            MacroState::Unread => {}
            MacroState::Reading => {
                self.close_cycle(i);
                return;
            }
            MacroState::Declared(_) | MacroState::Faulted => return,
        }
        self.states[i] = MacroState::Reading;
        self.stack.push(i);
        let mut reads = Vec::new();
        each_conjunct(self.macros[i].definition, &mut |conjunct| {
            if let Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) = conjunct {
                if let RelationRef::Lib(name) = &atom.value().relation {
                    if let Some(&j) = self.index.get(name) {
                        reads.push(j);
                    }
                }
            }
        });
        for &j in &reads {
            self.read(j);
        }
        self.stack.pop();
        let read_faulted = reads.iter().any(|&j| !matches!(self.states[j], MacroState::Declared(_)));
        if matches!(self.states[i], MacroState::Faulted) || read_faulted {
            self.states[i] = MacroState::Faulted;
            return;
        }
        let m = self.macros[i];
        let declaration = self.column_types(&m).and_then(|types| {
            let modes = self.modes_of(&m)?;
            let columns = m.columns.iter().zip(types).map(|((name, _), ty)| Column { name: name.clone(), ty: ColumnType::Fixed(ty) });
            Some(AlgebraRelation { columns: columns.collect(), modes })
        });
        self.states[i] = match declaration {
            Some(relation) => MacroState::Declared(relation),
            None => MacroState::Faulted,
        };
    }

    /// Gives a diagnostic at each macro of the cycle that a read of macro
    /// `i`, which is being read, closes, and marks each with a fault.
    fn close_cycle(&mut self, i: usize) {
        let start = self.stack.iter().position(|&j| j == i).expect("a macro being read stands on the stack");
        let cycle: Vec<usize> = self.stack[start..].to_vec();
        let names: Vec<String> = cycle.iter().map(|&j| format!("`{}`", self.macros[j].name.0)).collect();
        for &j in &cycle {
            if matches!(self.states[j], MacroState::Faulted) {
                continue;
            }
            self.states[j] = MacroState::Faulted;
            let message = format!("the macro `{}` reads itself through the macros {}", self.macros[j].name.0, names.join(", "));
            self.diagnostics.push(crate::read::check_error(CheckId::Cycles, message, self.macros[j].place));
        }
    }

    /// The type of each column of `m`, or `None` with a diagnostic for each
    /// column that has a fault.
    fn column_types(&mut self, m: &RelationMacro<'_>) -> Option<Box<[ValueType]>> {
        let mut types = Vec::new();
        let mut faulted = false;
        for (column, label) in m.columns {
            let message = match label_type(m.definition, *label, &|atom, column| self.site_type(atom, column)) {
                Ok(Some(ty)) => {
                    types.push(ty);
                    continue;
                }
                Ok(None) => "stands at no site that gives a type".to_string(),
                Err(fault) => label_fault_message(fault),
            };
            faulted = true;
            let message = format!("the label of the column `{}` of the macro `{}` {message}", column_display(column), m.name.0);
            self.diagnostics.push(crate::read::check_error(CheckId::Types, message, m.place));
        }
        if faulted { None } else { Some(types.into()) }
    }

    /// The modes of `m`, as [`macro_column_types`] gives them, or `None`
    /// with a diagnostic where no set of its columns grounds its definition.
    /// A set that holds a column of an orientation type grounds what the set
    /// without it grounds, so no mode holds one.
    fn modes_of(&mut self, m: &RelationMacro<'_>) -> Option<Box<[Mode]>> {
        let definition_labels = body_labels(m.definition);
        let label_types = |label: LabelId| label_type(m.definition, label, &|atom, column| self.site_type(atom, column)).ok().flatten();
        let atom_modes = |atom: &Atom| self.atom_modes(atom);
        let columns: Vec<usize> = (0..m.columns.len()).collect();
        let grounds = |set: &[usize]| {
            let grounded: StableHashSet<LabelId> = set.iter().map(|&c| m.columns[c].1).collect();
            let reached = grounded_labels(m.definition, &grounded, &atom_modes, &label_types);
            definition_labels.iter().all(|label| reached.contains(label))
        };
        let mut found: Vec<Vec<usize>> = Vec::new();
        for size in 0..=columns.len() {
            for set in subsets_of_size(&columns, size) {
                if found.iter().any(|mode| mode.iter().all(|c| set.contains(c))) {
                    continue;
                }
                if grounds(&set) {
                    found.push(set);
                }
            }
            if found.first().is_some_and(|mode| mode.is_empty()) {
                return Some(Box::default());
            }
        }
        if found.is_empty() {
            let message = format!("no set of the columns of the macro `{}` grounds every label of its definition", m.name.0);
            self.diagnostics.push(crate::read::check_error(CheckId::Grounding, message, m.place));
            return None;
        }
        let modes = found.into_iter().map(|set| Mode { grounded: set.into_iter().map(|c| m.columns[c].0.clone()).collect() });
        Some(modes.collect())
    }

    /// The modes of the relation `atom` reads: a macro's that has its
    /// declaration, or a lib relation's, and none for any other relation.
    fn atom_modes(&self, atom: &Atom) -> &[Mode] {
        let RelationRef::Lib(name) = &atom.relation else { return &[] };
        if let Some(&j) = self.index.get(name) {
            return &self.declared(j).modes;
        }
        self.modes.get(name).map_or(&[], |modes| modes)
    }

    /// The declaration of macro `j`, which a macro that reads it reads once
    /// it has one.
    fn declared(&self, j: usize) -> &AlgebraRelation {
        let MacroState::Declared(relation) = &self.states[j] else {
            unreachable!("a macro takes its declaration only after each macro it reads has one")
        };
        relation
    }

    /// The type of the column `path` gives of the relation `atom` reads,
    /// where that relation is a lib name of `lib` or a macro with its
    /// declaration and `path` is one column. A longer path, a field of a
    /// type parameter's column, gives no type.
    pub(super) fn site_type(&self, atom: &Atom, path: &[ColumnName]) -> Option<ValueType> {
        let [column] = path else { return None };
        let RelationRef::Lib(name) = &atom.relation else { return None };
        let columns: &[Column] = match self.index.get(name) {
            Some(&j) => match &self.states[j] {
                MacroState::Declared(relation) => &relation.columns,
                MacroState::Unread | MacroState::Reading | MacroState::Faulted => return None,
            },
            None => self.lib.get(name)?,
        };
        match &columns.iter().find(|c| &c.name == column)?.ty {
            ColumnType::Fixed(ty) | ColumnType::PoseOr(ty) => Some(ty.clone()),
            ColumnType::Pose | ColumnType::SharedPose | ColumnType::Parameter(_) => None,
        }
    }
}

/// The subsets of `items` of `size` elements, each in the order of `items`.
fn subsets_of_size(items: &[usize], size: usize) -> Vec<Vec<usize>> {
    if size == 0 {
        return vec![Vec::new()];
    }
    let mut subsets = Vec::new();
    for (i, &item) in items.iter().enumerate() {
        for mut rest in subsets_of_size(&items[i + 1..], size - 1) {
            rest.insert(0, item);
            subsets.push(rest);
        }
    }
    subsets
}

/// The text of `fault` of a label, for a diagnostic that names the label
/// before it.
pub(super) fn label_fault_message(fault: LabelFault) -> String {
    match fault {
        LabelFault::EmptyMeet(a, b) => format!("stands at sites of the types {a:?} and {b:?}, whose meet is empty"),
        LabelFault::NoJoin(a, b) => format!("takes the types {a:?} and {b:?} from two branches, which have no join"),
    }
}

/// The name of `column`, for a diagnostic.
pub(super) fn column_display(column: &ColumnName) -> String {
    match column {
        ColumnName::Written(name) => name.to_string(),
        ColumnName::Slot(slot) => format!("slot {slot}"),
    }
}
