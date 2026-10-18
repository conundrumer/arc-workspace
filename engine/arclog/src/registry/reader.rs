//! The reader of the two lib files, which reads each form into the
//! registry's records and gives a diagnostic at the form of each fault.

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
struct ComponentHead<'e> {
    name: LibName,
    kind: ComponentKind,
    type_parameters: Box<[TypeParameter]>,
    inputs: Box<[InputPort]>,
    outputs: &'e [SExpr],
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
    c4: Option<(Box<[Box<str>]>, SourcePlace)>,
    pub(super) facts: StableHashMap<FactRelation, Box<[Column]>>,
    pub(super) relation_macros: Vec<WrittenMacro>,
    /// Each `(proposer <name> arclog)` form's name and place, in file order.
    pub(super) arclog_proposers: Vec<(LibName, SourcePlace)>,
    pub(super) cells: Vec<WrittenCell>,
    pub(super) bodies: Vec<BodyInFile>,
}

impl FileReader {
    pub(super) fn fault(&mut self, check: CheckId, message: impl Into<Box<str>>, place: SourcePlace) {
        self.diagnostics.push(check_error(check, message, place));
    }

    /// Gives a diagnostic of the grammar, and `None`.
    fn refuse<T>(&mut self, message: impl Into<Box<str>>, place: SourcePlace) -> Option<T> {
        self.fault(CheckId::Grammar, message, place);
        None
    }

    /// `result`'s value, or `None` with its diagnostics added.
    fn read<T>(&mut self, result: Result<T, Vec<crate::diagnostic::Diagnostic>>) -> Option<T> {
        result.map_err(|diagnostics| self.diagnostics.extend(diagnostics)).ok()
    }

    /// The s-expressions of `text`, none where it does not read.
    pub(super) fn sexprs(&mut self, text: &str, file: SourceFile) -> Vec<SExpr> {
        self.read(read_sexprs(text, file)).map(|(exprs, _)| exprs).unwrap_or_default()
    }

    fn symbol<'e>(&mut self, expr: Option<&'e SExpr>, what: &str, at: SourcePlace) -> Option<&'e str> {
        match expr {
            Some(SExpr::Symbol { text, .. }) => Some(text),
            Some(other) => self.refuse(format!("{what} is a symbol"), other.place()),
            None => self.refuse(format!("the form lacks {what}"), at),
        }
    }

    /// The items after the head of `expr`, a list headed by `head`.
    fn headed<'e>(&mut self, expr: Option<&'e SExpr>, head: &str, at: SourcePlace) -> Option<&'e [SExpr]> {
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
    fn no_more(&mut self, exprs: &[SExpr]) -> Option<()> {
        match exprs.first() {
            Some(expr) => self.refuse("the form has no place for this item", expr.place()),
            None => Some(()),
        }
    }

    /// Records that a form at `place` declares `name`, or gives a fault
    /// where another form declares it.
    fn declare(&mut self, name: &LibName, place: SourcePlace) -> bool {
        if self.declared.insert(name.clone()) {
            return true;
        }
        self.fault(CheckId::Scope, format!("`{}` is declared by two forms", name.0), place);
        false
    }

    pub(super) fn form(&mut self, expr: &SExpr) {
        let place = expr.place();
        let SExpr::List { items, .. } = expr else {
            self.refuse::<()>("a form of the registry file is a list", place);
            return;
        };
        let rest = items.get(1..).unwrap_or_default();
        match head_of(expr) {
            Some(RELATION) => self.relation(rest, place),
            Some(COMPONENT) => {
                if let Some((name, component)) = self.component(rest, place)
                    && self.declare(&name, place)
                {
                    self.entries.insert(name, LibEntry::Component(component));
                }
                Some(())
            }
            Some(PROPOSER) => self.proposer(rest, place),
            Some(DERIVATION) => self.derivation(rest, place),
            Some(CONSTANTS) => self.constants(rest, place),
            Some(FACT) => self.fact(rest, place),
            Some(MACRO) => self.macro_form(rest, place),
            _ => self.refuse("the form's head is no kind of form of the registry file", place),
        };
    }

    /// The type that `expr` writes, with its type name where it writes one,
    /// for the reader of a default's rows.
    fn column_type(&mut self, expr: &SExpr, parameters: &[TypeParameter]) -> Option<(ColumnType, Option<TypeName>)> {
        if let Some(rest) = headed(expr, POSE_OR) {
            let name = match rest {
                [SExpr::Symbol { text, .. }] => spelling::parse(spelling::TYPE_NAMES, text),
                _ => None,
            };
            return match name {
                Some(name) => Some((ColumnType::PoseOr(name.value_type()), Some(name))),
                None => self.refuse(format!("a `({POSE_OR} <type>)` form holds one type name"), expr.place()),
            };
        }
        let text = self.symbol(Some(expr), "a type", expr.place())?;
        if let Some(name) = spelling::parse(spelling::TYPE_NAMES, text) {
            return Some((ColumnType::Fixed(name.value_type()), Some(name)));
        }
        match text {
            POSE => Some((ColumnType::Pose, None)),
            SHARED_POSE => Some((ColumnType::SharedPose, None)),
            _ => match parameters.iter().find(|p| &*p.0 == text) {
                Some(parameter) => Some((ColumnType::Parameter(parameter.clone()), None)),
                None => self.refuse(format!("`{text}` is no type and no type parameter of the component"), expr.place()),
            },
        }
    }

    /// The column that `expr`, `(<Column> <type>)`, writes.
    fn column(&mut self, expr: &SExpr, parameters: &[TypeParameter]) -> Option<(Column, Option<TypeName>)> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("a column is a list of its name and its type", expr.place());
        };
        let [name, ty] = &items[..] else {
            return self.refuse("a column is a list of its name and its type", *place);
        };
        let name = self.symbol(Some(name), "the column's name", *place)?;
        let (ty, written) = self.column_type(ty, parameters)?;
        Some((Column { name: ColumnName::Written(name.into()), ty }, written))
    }

    /// The columns that `expr`, `(<head> (<Column> <type>) ...)`, writes.
    fn columns(&mut self, expr: Option<&SExpr>, head: &str, parameters: &[TypeParameter], at: SourcePlace) -> Option<Box<[Column]>> {
        let items = self.headed(expr, head, at)?;
        let columns: Option<Vec<Column>> = items.iter().map(|item| self.column(item, parameters).map(|(c, _)| c)).collect();
        columns.map(Into::into)
    }

    /// `(relation <name> (columns ...) [(modes ...)])`, after its head.
    fn relation(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the relation's name", place)?.into());
        let columns = self.columns(rest.get(1), COLUMNS, &[], place)?;
        let modes = match rest.get(2) {
            Some(expr) => self.modes(expr, &columns, place)?,
            None => Box::default(),
        };
        self.no_more(rest.get(3..).unwrap_or_default())?;
        if self.declare(&name, place) {
            self.entries.insert(name, LibEntry::Relation(AlgebraRelation { columns, modes }));
        }
        Some(())
    }

    /// `(modes (<Column> ...) ...)`, each mode a nonempty list of columns of
    /// `columns`.
    fn modes(&mut self, expr: &SExpr, columns: &[Column], place: SourcePlace) -> Option<Box<[Mode]>> {
        let items = self.headed(Some(expr), MODES, place)?;
        let mut modes = Vec::new();
        for item in items {
            let SExpr::List { items: names, place, .. } = item else {
                return self.refuse("a mode is a list of columns", item.place());
            };
            if names.is_empty() {
                return self.refuse("a mode is not empty", *place);
            }
            let mut grounded = Vec::new();
            for name in names.iter() {
                let text = self.symbol(Some(name), "a mode's column", *place)?;
                let column = ColumnName::Written(text.into());
                if !columns.iter().any(|c| c.name == column) {
                    return self.refuse(format!("`{text}` is no column of the relation"), name.place());
                }
                grounded.push(column);
            }
            modes.push(Mode { grounded: grounded.into() });
        }
        Some(modes.into())
    }

    /// `(component <Name> <kind> (type-parameters ...) (inputs ...) (outputs ...))`,
    /// after its head.
    fn component_head<'e>(&mut self, rest: &'e [SExpr], place: SourcePlace) -> Option<ComponentHead<'e>> {
        let name = LibName(self.symbol(rest.first(), "the component's name", place)?.into());
        let kind_text = self.symbol(rest.get(1), "the component's kind", place)?;
        let Some(kind) = spelling::parse(COMPONENT_KINDS, kind_text) else {
            return self.refuse(format!("`{kind_text}` is no kind of component"), rest[1].place());
        };
        let parameters = self.headed(rest.get(2), TYPE_PARAMETERS, place)?;
        let parameters: Option<Vec<TypeParameter>> =
            parameters.iter().map(|p| self.symbol(Some(p), "a type parameter", place).map(|t| TypeParameter(t.into()))).collect();
        let type_parameters: Box<[TypeParameter]> = parameters?.into();
        let inputs = self.headed(rest.get(3), INPUTS, place)?;
        let inputs: Option<Vec<InputPort>> = inputs.iter().map(|input| self.input(input, &type_parameters)).collect();
        let outputs = self.headed(rest.get(4), OUTPUTS, place)?;
        self.no_more(rest.get(5..).unwrap_or_default())?;
        Some(ComponentHead { name, kind, type_parameters, inputs: inputs?.into(), outputs })
    }

    /// `(component <Name> <kind> (type-parameters ...) (inputs ...) (outputs ...))`,
    /// after its head, each output column with its type.
    fn component(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<(LibName, Component)> {
        let head = self.component_head(rest, place)?;
        let outputs: Option<Vec<Port>> = head.outputs.iter().map(|output| self.port(output, &head.type_parameters)).collect();
        let component = Component { kind: head.kind, type_parameters: head.type_parameters, inputs: head.inputs, outputs: outputs?.into() };
        Some((head.name, component))
    }

    /// An output, `(<output> (<column> <type>) ...)`.
    fn port(&mut self, expr: &SExpr, parameters: &[TypeParameter]) -> Option<Port> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("a port is a list of its name and its columns", expr.place());
        };
        let name = PortName(self.symbol(items.first(), "the port's name", *place)?.into());
        let columns: Option<Vec<Column>> = items[1..].iter().map(|item| self.column(item, parameters).map(|(c, _)| c)).collect();
        Some(Port { name, columns: columns?.into() })
    }

    /// An input, `(<input> (<column> <type>) ... [(default <rows>)] [reads-outputs])`.
    fn input(&mut self, expr: &SExpr, parameters: &[TypeParameter]) -> Option<InputPort> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("an input is a list of its name and its columns", expr.place());
        };
        let name = PortName(self.symbol(items.first(), "the input's name", *place)?.into());
        let mut rest = &items[1..];
        let reads_outputs = matches!(rest.last(), Some(SExpr::Symbol { text, .. }) if &**text == READS_OUTPUTS);
        if reads_outputs {
            rest = &rest[..rest.len() - 1];
        }
        let default_rows = rest.last().and_then(|last| headed(last, DEFAULT));
        if default_rows.is_some() {
            rest = &rest[..rest.len() - 1];
        }
        let mut columns = Vec::new();
        let mut written = Vec::new();
        for item in rest {
            let (column, name) = self.column(item, parameters)?;
            columns.push(column);
            written.push(name);
        }
        let default = match default_rows {
            Some(rows) => Some(DefaultRows { written: self.read(read_param_value(rows, &written))? }),
            None => None,
        };
        Some(InputPort { port: Port { name, columns: columns.into() }, default, reads_outputs })
    }

    /// `(proposer <name> native (columns ...))` or `(proposer <name> arclog)`,
    /// after its head.
    fn proposer(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the proposer's name", place)?.into());
        match self.symbol(rest.get(1), "the proposer's kind", place)? {
            NATIVE => {
                let columns = self.columns(rest.get(2), COLUMNS, &[], place)?;
                self.no_more(rest.get(3..).unwrap_or_default())?;
                if self.declare(&name, place) {
                    self.entries.insert(name, LibEntry::Proposer(Proposer::Native { columns }));
                }
            }
            ARCLOG => {
                self.no_more(rest.get(2..).unwrap_or_default())?;
                if self.declare(&name, place) {
                    self.arclog_proposers.push((name, place));
                }
            }
            other => return self.refuse(format!("`{other}` is no kind of proposer, `{NATIVE}` or `{ARCLOG}`"), rest[1].place()),
        }
        Some(())
    }

    /// `(derivation <Name> (fields ...) (columns ...))`, after its head.
    fn derivation(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the derivation's name", place)?.into());
        let fields = self.columns(rest.get(1), FIELDS, &[], place)?;
        let columns = self.columns(rest.get(2), COLUMNS, &[], place)?;
        self.no_more(rest.get(3..).unwrap_or_default())?;
        match self.derivations.entry(name) {
            std::collections::hash_map::Entry::Occupied(entry) => {
                let message = format!("`{}` is declared by two `derivation` forms", entry.key().0);
                self.fault(CheckId::Scope, message, place);
            }
            std::collections::hash_map::Entry::Vacant(entry) => {
                entry.insert(Derivation { fields, columns });
            }
        }
        Some(())
    }

    /// `(constants <type> <NAME> ...)` or `(constants C4 <NAME> ...)`, after
    /// its head.
    fn constants(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let ty_text = self.symbol(rest.first(), "the constants' type", place)?;
        let names: Option<Vec<Box<str>>> =
            rest[1..].iter().map(|name| self.symbol(Some(name), "a constant's name", place).map(Into::into)).collect();
        let names: Box<[Box<str>]> = names?.into();
        if ty_text == C4 {
            if self.c4.is_some() {
                return self.refuse("the file has two `C4` forms", place);
            }
            self.c4 = Some((names, place));
            return Some(());
        }
        let Some(ty) = spelling::parse(spelling::TYPE_NAMES, ty_text).and_then(orientation_type) else {
            return self.refuse(format!("`{ty_text}` is no orientation type and not `{C4}`"), rest[0].place());
        };
        if self.constants.contains_key(&ty) {
            return self.refuse(format!("the file has two `constants` forms of `{ty_text}`"), place);
        }
        if names.len() > usize::from(u8::MAX) + 1 {
            return self.refuse("an orientation type has at most 256 constants", place);
        }
        for (index, name) in names.iter().enumerate() {
            let earlier = names[..index].contains(name) || self.constants.values().any(|c| c.names.contains(name));
            if earlier {
                self.fault(CheckId::Scope, format!("the constant `{name}` is written twice"), place);
            }
        }
        let set = (0..names.len()).map(|index| OrientationConstant::new(ty, index as u8)).collect();
        self.constants.insert(ty, TypeConstants { names, set: ConstantSet { constants: set } });
        Some(())
    }

    /// `(fact <name> (columns ...))`, after its head.
    fn fact(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let text = self.symbol(rest.first(), "the fact's name", place)?;
        let Some(fact) = spelling::parse(spelling::FACT_RELATIONS, text) else {
            return self.refuse(format!("`{text}` is no fact relation"), rest[0].place());
        };
        let columns = self.columns(rest.get(1), COLUMNS, &[], place)?;
        self.no_more(rest.get(2..).unwrap_or_default())?;
        if self.facts.insert(fact, columns).is_some() {
            return self.refuse(format!("the file has two `fact` forms of `{text}`"), place);
        }
        Some(())
    }

    /// `(macro <name> (columns ...) <body>)` or a cell instance,
    /// `(macro <name> (component ...) ...)`, after its head.
    fn macro_form(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the macro's name", place)?.into());
        match rest.get(1).and_then(head_of) {
            Some(COLUMNS) => self.relation_macro(name, rest, place),
            Some(COMPONENT) => self.cell_instance(name, rest, place),
            _ => self.refuse(format!("a macro's name stands before its `({COLUMNS} ...)` or its `({COMPONENT} ...)` form"), place),
        }
    }

    /// The label of `labels` named `name`, the first that stands, or a fault
    /// that `what` stands for no label of the body.
    fn label_of(&mut self, labels: &crate::read::LabelNames, name: &str, what: &str, place: SourcePlace) -> Option<LabelId> {
        match labels.iter().find(|(n, _)| &**n == name) {
            Some((_, label)) => Some(*label),
            None => {
                self.fault(CheckId::Scope, format!("{what} stands for the label `{name}`, which its body holds no label of"), place);
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
        let (definition, labels) = self.read(read_body(&rest[2..], None))?;
        let columns = self.label_columns(written, &labels, &format!("the macro `{}`", name.0), place)?;
        if self.declare(&name, place) {
            self.bodies.push(BodyInFile { body: definition.clone(), place, cell: None });
            self.relation_macros.push(WrittenMacro { name, place, columns, definition });
        }
        Some(())
    }

    /// `(macro <Name> (component ...) [(INIT ...)] (RULE &<rule> <body>) ... (output <port> <body>) ...)`.
    fn cell_instance(&mut self, name: LibName, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let declaration = headed(&rest[1], COMPONENT).expect("the form's `component` form");
        let head = self.component_head(declaration, rest[1].place())?;
        if head.name != name {
            return self.refuse(format!("the cell instance `{}` declares the component `{}`", name.0, head.name.0), place);
        }
        let mut declared_ports = Vec::new();
        for item in head.outputs {
            let SExpr::List { items, place: at, .. } = item else {
                return self.refuse("an output is a list of its name and its columns", item.place());
            };
            let port = self.symbol(items.first(), "the output's port", *at)?;
            declared_ports.push((PortName(port.into()), &items[1..]));
        }
        let mut rest = &rest[2..];
        let init = rest.first().filter(|expr| head_of(expr) == Some(spelling::INIT));
        let cell = self.cells.len();
        let mut bodies = Vec::new();
        let definition = match init {
            Some(expr) => {
                rest = &rest[1..];
                let (instance, _) = self.read(read_instance(expr))?;
                let value = instance.value();
                let key = value.key.iter().flat_map(|key| {
                    let key = key.value();
                    std::iter::once(key.key.body.clone()).chain(key.inputs.iter().map(|input| input.value().body.clone()))
                });
                bodies.extend(key.chain(value.inputs.iter().map(|input| input.value().body.clone())));
                CellDefinition::Instance(instance.clone())
            }
            None => CellDefinition::Relation,
        };
        let mut rules = Vec::new();
        while let Some(rule) = rest.first().and_then(|expr| headed(expr, spelling::spelling(spelling::CLAUSE_KEYWORDS, &ClauseKeyword::Rule))) {
            rest = &rest[1..];
            let text = self.symbol(rule.first(), "the rule's name", place)?;
            if !text.starts_with(spelling::DECLARED_MARK) {
                return self.refuse(format!("`{text}` is not a declared name, `&` and a name"), place);
            }
            let rule_name = RelationName(DeclaredName::Written(text.into()));
            let (body, labels) = self.read(read_body(&rule[1..], init))?;
            let columns = labels.iter().map(|(n, label)| (ColumnName::Written(n.clone()), *label)).collect();
            bodies.push(body.clone());
            rules.push((CellRule { name: rule_name, body }, columns));
        }
        let mut outputs: Vec<(PortName, LabelColumns, Node<Body>)> = Vec::new();
        for expr in rest {
            let Some(output) = headed(expr, OUTPUT) else {
                return self.refuse(format!("a cell instance's form after its `RULE` forms is an `({OUTPUT} ...)` form"), expr.place());
            };
            let port = PortName(self.symbol(output.first(), "the output's port", place)?.into());
            let Some((_, declared)) = declared_ports.iter().find(|(p, _)| *p == port) else {
                return self.refuse(format!("`{}` is no output of the cell instance `{}`", port.0, name.0), expr.place());
            };
            if outputs.iter().any(|(p, _, _)| *p == port) {
                return self.refuse(format!("the output `{}` of the cell instance `{}` has two `({OUTPUT} ...)` forms", port.0, name.0), expr.place());
            }
            let (body, labels) = self.read(read_body(&output[1..], init))?;
            let what = format!("the output `{}` of the cell instance `{}`", port.0, name.0);
            let columns = self.label_columns(declared, &labels, &what, place)?;
            bodies.push(body.clone());
            outputs.push((port, columns, body));
        }
        for (port, _) in &declared_ports {
            if !outputs.iter().any(|(p, _, _)| p == port) {
                return self.refuse(format!("the output `{}` of the cell instance `{}` has no `({OUTPUT} ...)` form", port.0, name.0), place);
            }
        }
        if self.declare(&name, place) {
            self.bodies.extend(bodies.into_iter().map(|body| BodyInFile { body, place, cell: Some(cell) }));
            self.cells.push(WrittenCell {
                name,
                place,
                kind: head.kind,
                type_parameters: head.type_parameters,
                inputs: head.inputs,
                definition,
                rules: rules.into(),
                outputs: outputs.into(),
            });
        }
        Some(())
    }

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
            let Some((body, labels)) = self.read(read_body(&rest[1..], None)) else { continue };
            if clauses.iter().any(|(n, _, _)| *n == name) {
                self.fault(CheckId::Scope, format!("the proposer `{}` has two clauses", name.0), place);
                continue;
            }
            let columns = labels.iter().map(|(n, _)| ColumnName::Written(n.clone())).collect();
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
