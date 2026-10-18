//! The reader of the two lib files, which reads each form into the
//! registry's records and gives a diagnostic at the form of each fault: the
//! spellings of the forms, the records of a read form, the reader's state
//! and its helpers, the declaration of the macros, the completeness check of
//! the accessors and the assembly of the registry.

use super::*;

// The words of the registry file's forms.
pub(super) const RELATION: &str = "relation";
pub(super) const COMPONENT: &str = "component";
pub(super) const PROPOSER: &str = "proposer";
pub(super) const DERIVATION: &str = "derivation";
pub(super) const CONSTANTS: &str = "constants";
pub(super) const FACT: &str = "fact";
pub(super) const MACRO: &str = "macro";
pub(super) const COLUMNS: &str = "columns";
pub(super) const MODES: &str = "modes";
pub(super) const FIELDS: &str = "fields";
pub(super) const TYPE_PARAMETERS: &str = "type-parameters";
pub(super) const INPUTS: &str = "inputs";
pub(super) const OUTPUTS: &str = "outputs";
pub(super) const DEFAULT: &str = "default";
pub(super) const READS_OUTPUTS: &str = "reads-outputs";
pub(super) const NATIVE: &str = "native";
pub(super) const ARCLOG: &str = "arclog";
pub(super) const OUTPUT: &str = "output";
pub(super) const POSE: &str = "Pose";
pub(super) const SHARED_POSE: &str = "shared-pose";
pub(super) const POSE_OR: &str = "pose-or";
pub(super) const C4: &str = "C4";

pub(super) const COMPONENT_KINDS: &[(ComponentKind, &str)] = &[
    (ComponentKind::Construction, "construction"),
    (ComponentKind::Detector, "detector"),
    (ComponentKind::TaskStructure, "task-structure"),
];

/// The orientation type whose constants a column of `name` holds, where
/// `name` is one: `C4` is a part of `D4`, and `Dir8` and `Axis4` are unions.
pub(super) fn orientation_type(name: TypeName) -> Option<OrientationType> {
    match name {
        TypeName::Dir => Some(OrientationType::Dir),
        TypeName::DiagDir => Some(OrientationType::DiagDir),
        TypeName::Axis => Some(OrientationType::Axis),
        TypeName::DiagAxis => Some(OrientationType::DiagAxis),
        TypeName::D4 => Some(OrientationType::D4),
        TypeName::Sym => Some(OrientationType::Sym),
        TypeName::Sense => Some(OrientationType::Sense),
        TypeName::Number
        | TypeName::Color
        | TypeName::Example
        | TypeName::Unit
        | TypeName::Box
        | TypeName::Position
        | TypeName::Offset
        | TypeName::Ident
        | TypeName::C4
        | TypeName::Dir8
        | TypeName::Axis4 => None,
    }
}

/// The items of `expr` after its head, where it is a list headed by `head`.
pub(super) fn headed<'e>(expr: &'e SExpr, head: &str) -> Option<&'e [SExpr]> {
    match expr {
        SExpr::List { items, .. } => match items.split_first() {
            Some((SExpr::Symbol { text, .. }, rest)) if &**text == head => Some(rest),
            _ => None,
        },
        _ => None,
    }
}

/// The place of the start of `file`, where a fault of no one form stands.
pub(super) fn file_start(file: SourceFile) -> SourcePlace {
    SourcePlace { file, start: 0, end: 0, line: 1, column: 1 }
}

/// A relation macro as its form writes it, before its declaration.
pub(super) struct WrittenMacro {
    pub(super) name: LibName,
    pub(super) place: SourcePlace,
    pub(super) columns: LabelColumns,
    pub(super) definition: Node<Body>,
}

/// Each column of a form, with the label of the form's body that the
/// column stands for.
pub(super) type LabelColumns = Box<[(ColumnName, LabelId)]>;

/// A cell instance as its form writes it, before its outputs' column types:
/// what its bodies read beside the names of the lib, its own inputs, its
/// `RULE` forms with their columns and its `INIT` form, and each output's
/// port with the label each of its columns stands for.
pub(super) struct WrittenCell {
    pub(super) name: LibName,
    pub(super) place: SourcePlace,
    pub(super) kind: ComponentKind,
    pub(super) type_parameters: Box<[TypeParameter]>,
    pub(super) inputs: Box<[InputPort]>,
    pub(super) definition: CellDefinition,
    /// Each `RULE` form, with each of its columns and the label of its body
    /// that the column is.
    pub(super) rules: Box<[(CellRule, LabelColumns)]>,
    /// Each output, with each column of its port and the label of its body
    /// that the column stands for.
    pub(super) outputs: Box<[(PortName, LabelColumns, Node<Body>)]>,
}

impl WrittenCell {
    /// The `INIT` form, where the cell instance has one.
    pub(super) fn init(&self) -> Option<&crate::program::Instance> {
        match &self.definition {
            CellDefinition::Instance(instance) => Some(instance.value()),
            CellDefinition::Relation => None,
        }
    }
}

/// A `component` form's name, kind, type parameters and inputs, and the
/// items of its `outputs` form, which a component's form writes with their
/// types and a cell instance's with their labels.
pub(super) struct ComponentHead<'e> {
    pub(super) name: LibName,
    pub(super) kind: ComponentKind,
    pub(super) type_parameters: Box<[TypeParameter]>,
    pub(super) inputs: Box<[InputPort]>,
    pub(super) outputs: &'e [SExpr],
}

/// A `(proposer <name> arclog (columns <Label> ...))` form: the proposer's
/// name, the place of its form, and the labels it names, in the order the
/// form gives them.
pub(super) struct ArclogProposer {
    pub(super) name: LibName,
    pub(super) place: SourcePlace,
    pub(super) columns: Box<[Box<str>]>,
}

/// A body of either file, whose reads [`FileReader::check_reads`] checks
/// once every form is read: the place of its form, and the index of the
/// cell instance it stands in, where it stands in one.
pub(super) struct BodyInFile {
    pub(super) body: Node<Body>,
    pub(super) place: SourcePlace,
    pub(super) cell: Option<usize>,
}

/// The reader of the two lib files. It reads each form whatever an earlier
/// one gave, and adds each fault of either file to one list.
#[derive(Default)]
pub(super) struct FileReader {
    pub(super) diagnostics: Vec<crate::diagnostic::Diagnostic>,
    pub(super) entries: StableHashMap<LibName, LibEntry>,
    /// Each name that a form of the entries declares, a relation macro's and
    /// an arclog proposer's among them, which take their entries later.
    pub(super) declared: StableHashSet<LibName>,
    pub(super) derivations: StableHashMap<LibName, Derivation>,
    pub(super) constants: StableHashMap<OrientationType, TypeConstants>,
    /// The names of the `C4` form, and its place.
    pub(super) c4: Option<(Box<[Box<str>]>, SourcePlace)>,
    pub(super) facts: StableHashMap<FactRelation, Box<[Column]>>,
    pub(super) relation_macros: Vec<WrittenMacro>,
    /// Each `(proposer <name> arclog (columns ...))` form, in file order.
    pub(super) arclog_proposers: Vec<ArclogProposer>,
    pub(super) cells: Vec<WrittenCell>,
    pub(super) bodies: Vec<BodyInFile>,
}

impl FileReader {
    pub(super) fn fault(&mut self, check: CheckId, message: impl Into<Box<str>>, place: SourcePlace) {
        self.diagnostics.push(check_error(check, message, place));
    }

    /// Gives a diagnostic of the grammar, and `None`.
    pub(super) fn refuse<T>(&mut self, message: impl Into<Box<str>>, place: SourcePlace) -> Option<T> {
        self.fault(CheckId::Grammar, message, place);
        None
    }

    /// `result`'s value, or `None` with its diagnostics added.
    pub(super) fn read<T>(&mut self, result: Result<T, Vec<crate::diagnostic::Diagnostic>>) -> Option<T> {
        result.map_err(|diagnostics| self.diagnostics.extend(diagnostics)).ok()
    }

    /// The s-expressions of `text`, none where it does not read.
    pub(super) fn sexprs(&mut self, text: &str, file: SourceFile) -> Vec<SExpr> {
        self.read(read_sexprs(text, file)).map(|(exprs, _)| exprs).unwrap_or_default()
    }

    pub(super) fn symbol<'e>(&mut self, expr: Option<&'e SExpr>, what: &str, at: SourcePlace) -> Option<&'e str> {
        match expr {
            Some(SExpr::Symbol { text, .. }) => Some(text),
            Some(other) => self.refuse(format!("{what} is a symbol"), other.place()),
            None => self.refuse(format!("the form lacks {what}"), at),
        }
    }

    /// The items after the head of `expr`, a list headed by `head`.
    pub(super) fn headed<'e>(&mut self, expr: Option<&'e SExpr>, head: &str, at: SourcePlace) -> Option<&'e [SExpr]> {
        match expr {
            Some(expr) => match headed(expr, head) {
                Some(rest) => Some(rest),
                None => self.refuse(format!("a `({head} ...)` form stands here"), expr.place()),
            },
            None => self.refuse(format!("the form lacks its `({head} ...)` form"), at),
        }
    }

    /// Gives a diagnostic at each item of `exprs`, which the form has no
    /// place for.
    pub(super) fn no_more(&mut self, exprs: &[SExpr]) -> Option<()> {
        match exprs.first() {
            Some(expr) => self.refuse("the form has no place for this item", expr.place()),
            None => Some(()),
        }
    }

    /// Records that a form at `place` declares `name`, or gives a fault
    /// where another form declares it.
    pub(super) fn declare(&mut self, name: &LibName, place: SourcePlace) -> bool {
        if self.declared.insert(name.clone()) {
            return true;
        }
        self.fault(CheckId::Scope, format!("`{}` is declared by two forms", name.0), place);
        false
    }

    /// Gives each relation macro its declaration and each cell instance its
    /// output ports, as [`macro_column_types`] derives them from the columns
    /// of the other forms' names, the modes of the `relation` forms and the
    /// components.
    pub(super) fn declare_macros(&mut self) {
        let mut lib: StableHashMap<LibName, Box<[Column]>> = StableHashMap::default();
        let mut modes: StableHashMap<LibName, Box<[Mode]>> = StableHashMap::default();
        let mut components: StableHashMap<LibName, Component> = StableHashMap::default();
        for (name, entry) in &self.entries {
            match entry {
                LibEntry::Relation(relation) => {
                    lib.insert(name.clone(), relation.columns.clone());
                    modes.insert(name.clone(), relation.modes.clone());
                }
                LibEntry::Proposer(Proposer::Native { columns }) => {
                    lib.insert(name.clone(), columns.clone());
                }
                LibEntry::Component(component) => {
                    components.insert(name.clone(), component.clone());
                }
                LibEntry::Proposer(Proposer::Arclog { .. }) | LibEntry::Macro(_) => {}
            }
        }
        let macros: Vec<RelationMacro<'_>> = self
            .relation_macros
            .iter()
            .map(|m| RelationMacro { name: &m.name, place: m.place, columns: &m.columns, definition: m.definition.value() })
            .collect();
        let cells: Vec<CellMacro<'_>> = self
            .cells
            .iter()
            .map(|cell| CellMacro {
                name: &cell.name,
                place: cell.place,
                type_parameters: &cell.type_parameters,
                inputs: &cell.inputs,
                init: cell.init(),
                rules: cell.rules.iter().map(|(rule, columns)| (&rule.name, CellForm { columns, body: rule.body.value() })).collect(),
                outputs: cell.outputs.iter().map(|(port, columns, body)| (port, CellForm { columns, body: body.value() })).collect(),
            })
            .collect();
        let declarations = macro_column_types(&macros, &cells, &lib, &modes, &components);
        match declarations {
            Ok(mut declarations) => {
                for m in std::mem::take(&mut self.relation_macros) {
                    let relation = declarations.relations.remove(&m.name).expect("each relation macro takes a declaration");
                    let labels = m.columns.iter().map(|(_, label)| *label).collect();
                    self.entries.insert(m.name, LibEntry::Macro(Macro::Relation { relation, labels, definition: m.definition }));
                }
                for cell in std::mem::take(&mut self.cells) {
                    let ports = declarations.cells.remove(&cell.name).expect("each cell instance takes its output ports");
                    let component = Component { kind: cell.kind, type_parameters: cell.type_parameters, inputs: cell.inputs, outputs: ports };
                    let outputs = cell.outputs.into_iter().map(|(port, columns, body)| CellOutput { port, labels: columns.iter().map(|(_, label)| *label).collect(), body });
                    let rules = cell.rules.into_iter().map(|(rule, _)| rule).collect();
                    let instance = Macro::CellInstance { component, definition: cell.definition, rules, outputs: outputs.collect() };
                    self.entries.insert(cell.name, LibEntry::Macro(instance));
                }
            }
            Err(diagnostics) => self.diagnostics.extend(diagnostics),
        }
    }

    /// Gives a diagnostic where an accessor of the registry would have no
    /// value to give: an orientation type with no `constants` form, no `C4`
    /// form or a `C4` constant that is no D4 constant, or a fact relation
    /// with no `fact` form.
    pub(super) fn check_complete(&mut self) {
        let start = file_start(SourceFile::LibRegistry);
        for (name, text) in spelling::TYPE_NAMES {
            if orientation_type(*name).is_some_and(|ty| !self.constants.contains_key(&ty)) {
                self.fault(CheckId::Scope, format!("the file has no `constants` form of `{text}`"), start);
            }
        }
        match &self.c4 {
            Some((names, place)) => {
                let d4 = self.constants.get(&OrientationType::D4);
                let outside: Vec<String> = names
                    .iter()
                    .filter(|name| d4.is_none_or(|d4| !d4.names.contains(name)))
                    .map(|name| format!("the `C4` constant `{name}` is no `D4` constant"))
                    .collect();
                let place = *place;
                for message in outside {
                    self.fault(CheckId::Scope, message, place);
                }
            }
            None => self.fault(CheckId::Scope, "the file has no `C4` form", start),
        }
        for (fact, text) in spelling::FACT_RELATIONS {
            if !self.facts.contains_key(fact) {
                self.fault(CheckId::Scope, format!("the file has no `fact` form of `{text}`"), start);
            }
        }
    }

    /// The registry read, or the diagnostics of each fault of either file.
    pub(super) fn registry(self) -> Result<Registry, RegistryError> {
        if !self.diagnostics.is_empty() {
            return Err(RegistryError { diagnostics: self.diagnostics });
        }
        let d4 = self.constants.get(&OrientationType::D4).expect("`check_complete` faults where `D4` has no `constants` form");
        let (names, _) = self.c4.as_ref().expect("`check_complete` faults where the file has no `C4` form");
        let c4 = names.iter().filter_map(|name| d4.constant(OrientationType::D4, name)).collect();
        Ok(Registry {
            entries: self.entries,
            derivations: self.derivations,
            constants: self.constants,
            c4: ConstantSet { constants: c4 },
            facts: self.facts,
        })
    }
}
