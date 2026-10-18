//! The derivation of a cell instance's output column types from its
//! definition: the binding of the underlying construction's type parameters
//! by the `INIT` form, the column types of the `RULE` forms, and the type of
//! each output column, as [`super::macro_column_types`] gives them.

use std::cell::{Cell, RefCell};

use super::column_types::{column_display, label_fault_message, MacroDerivation};
use super::*;
use crate::types::{use_label, FieldName, Meet};

/// A cell instance of the file, as [`super::macro_column_types`] reads it.
#[derive(Clone, Debug)]
pub struct CellMacro<'a> {
    pub name: &'a LibName,
    /// The place of the cell instance's form, where a diagnostic on it
    /// stands.
    pub place: SourcePlace,
    pub type_parameters: &'a [TypeParameter],
    /// The inputs in the order the component declares them.
    pub inputs: &'a [InputPort],
    /// The `INIT` form, where the cell instance has one.
    pub init: Option<&'a crate::program::Instance>,
    /// Each `RULE` form's name and its columns, the labels of its body.
    pub rules: Box<[(&'a RelationName, CellForm<'a>)]>,
    /// Each output's port and its body, with the label each column of the
    /// port stands for.
    pub outputs: Box<[(&'a PortName, CellForm<'a>)]>,
}

/// A body of a cell instance whose labels stand for columns: a `RULE` form
/// or an output.
#[derive(Clone, Copy, Debug)]
pub struct CellForm<'a> {
    /// Each column's name and the label of the body it stands for, in the
    /// order of the columns.
    pub columns: &'a [(ColumnName, LabelId)],
    pub body: &'a Body,
}

/// The type a site of a cell instance's body gives a label: a fixed type,
/// or a type parameter of the cell instance.
#[derive(Clone, PartialEq, Eq, Debug)]
enum SiteType {
    Fixed(ValueType),
    Parameter(TypeParameter),
}

impl SiteType {
    /// The type of a lib column of `ty`, where it gives one to a cell
    /// instance's site.
    fn of_column(ty: &ColumnType) -> Option<SiteType> {
        match ty {
            ColumnType::Fixed(ty) | ColumnType::PoseOr(ty) => Some(SiteType::Fixed(ty.clone())),
            ColumnType::Parameter(parameter) => Some(SiteType::Parameter(parameter.clone())),
            ColumnType::Pose | ColumnType::SharedPose => None,
        }
    }

    fn column_type(self) -> ColumnType {
        match self {
            SiteType::Fixed(ty) => ColumnType::Fixed(ty),
            SiteType::Parameter(parameter) => ColumnType::Parameter(parameter),
        }
    }
}

/// What the `INIT` form binds a type parameter of the underlying
/// construction to: the type of one label, or a record of named fields
/// (`docs/arclog/arclog.md#instance`). A field may be a type parameter of
/// the cell instance, which [`ValueType::Record`] holds no place for.
#[derive(Clone, Debug)]
enum Binding {
    One(SiteType),
    Record(Box<[(FieldName, SiteType)]>),
}

/// What the `INIT` form's binding gives a column of one of its outputs:
/// a type, or the record bound to the column's type parameter.
enum InitColumn<'s> {
    Type(SiteType),
    Record(&'s TypeParameter, &'s [(FieldName, SiteType)]),
}

/// Where the derivation stands in its typing of one form of a cell
/// instance: its `INIT` form or a `RULE` form.
#[derive(Clone, Debug)]
enum FormState<T> {
    Unread,
    /// The forms it reads are being typed, so a read of it now closes a
    /// cycle, and that read's sites give no type.
    Reading,
    Typed(T),
}

/// A form of a cell instance that a body reads.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum CellRead {
    Init,
    Rule(usize),
}

/// The underlying construction of an `INIT` form: its type parameters, its
/// inputs, and its outputs with their column types.
#[derive(Clone, Copy)]
pub(super) struct Construction<'a> {
    pub(super) type_parameters: &'a [TypeParameter],
    pub(super) inputs: &'a [InputPort],
    pub(super) outputs: &'a [Port],
}

/// The derivation of one cell instance's output ports.
pub(super) struct CellDerivation<'a, 'b> {
    macros: &'a MacroDerivation<'a, 'b>,
    cell: &'a CellMacro<'b>,
    construction: Option<Construction<'a>>,
    init: FormState<Box<[(TypeParameter, Binding)]>>,
    /// The type of each column of each `RULE` form, `None` at a column with
    /// a fault.
    rules: Vec<FormState<Box<[Option<SiteType>]>>>,
    faults: RefCell<Vec<(CheckId, String)>>,
}

impl<'a, 'b> CellDerivation<'a, 'b> {
    /// The output ports of `cell`, with their column types, or `None` with a
    /// diagnostic at its form for each fault. `construction` is the
    /// component its `INIT` form instantiates, where it has one.
    pub(super) fn ports(
        macros: &'a MacroDerivation<'a, 'b>,
        cell: &'a CellMacro<'b>,
        construction: Option<Construction<'a>>,
        diagnostics: &mut Vec<crate::diagnostic::Diagnostic>,
    ) -> Option<Box<[Port]>> {
        let mut derivation = CellDerivation {
            macros,
            cell,
            construction,
            init: FormState::Unread,
            rules: vec![FormState::Unread; cell.rules.len()],
            faults: RefCell::new(Vec::new()),
        };
        if cell.init.is_some() {
            derivation.type_form(CellRead::Init);
        }
        for i in 0..cell.rules.len() {
            derivation.type_form(CellRead::Rule(i));
        }
        derivation.check_fields();
        let mut ports = Vec::new();
        for (port, form) in cell.outputs.iter() {
            let what = |column: &ColumnName| format!("the column `{}` of the output `{}`", column_display(column), port.0);
            let types = derivation.column_types(form, &what);
            let columns = form.columns.iter().zip(types).map(|((name, _), ty)| ty.map(|ty| Column { name: name.clone(), ty: ty.column_type() }));
            if let Some(columns) = columns.collect::<Option<Box<[Column]>>>() {
                ports.push(Port { name: (*port).clone(), columns });
            }
        }
        let faults = derivation.faults.into_inner();
        let faulted = !faults.is_empty();
        for (check, message) in faults {
            diagnostics.push(crate::read::check_error(check, format!("in the cell instance `{}`, {message}", cell.name.0), cell.place));
        }
        if faulted { None } else { Some(ports.into()) }
    }

    fn fault(&self, check: CheckId, message: String) {
        self.faults.borrow_mut().push((check, message));
    }

    /// Types `form` after each form it reads, where it is not typed yet.
    fn type_form(&mut self, form: CellRead) {
        let state_is_unread = match form {
            CellRead::Init => matches!(self.init, FormState::Unread),
            CellRead::Rule(i) => matches!(self.rules[i], FormState::Unread),
        };
        if !state_is_unread {
            return;
        }
        match form {
            CellRead::Init => self.init = FormState::Reading,
            CellRead::Rule(i) => self.rules[i] = FormState::Reading,
        }
        let bodies = self.bodies_of(form);
        for read in self.reads(&bodies) {
            self.type_form(read);
        }
        match form {
            CellRead::Init => {
                let bindings = self.bind();
                self.init = FormState::Typed(bindings);
            }
            CellRead::Rule(i) => {
                let (name, rule) = &self.cell.rules[i];
                let rule_name = crate::write::relation_ref(&RelationRef::Declared((*name).clone()));
                let what = |column: &ColumnName| format!("the column `{}` of the rule `{rule_name}`", column_display(column));
                let types = self.column_types(rule, &what);
                self.rules[i] = FormState::Typed(types.into());
            }
        }
    }

    /// The bodies of `form`: the `INIT` form's key body and input bodies, or
    /// a `RULE` form's body.
    fn bodies_of(&self, form: CellRead) -> Vec<&'b Body> {
        match form {
            CellRead::Init => {
                let Some(init) = self.cell.init else { return Vec::new() };
                let mut bodies = Vec::new();
                if let Some(key) = &init.key {
                    let key = key.value();
                    bodies.push(key.key.body.value());
                    bodies.extend(key.inputs.iter().map(|input| input.value().body.value()));
                }
                bodies.extend(init.inputs.iter().map(|input| input.value().body.value()));
                bodies
            }
            CellRead::Rule(i) => vec![self.cell.rules[i].1.body],
        }
    }

    /// The forms of the cell instance that `bodies` read, in the order of
    /// their reads.
    fn reads(&self, bodies: &[&Body]) -> Vec<CellRead> {
        let mut reads = Vec::new();
        for body in bodies {
            each_conjunct(body, &mut |conjunct| {
                let (Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom))) = conjunct else { return };
                let read = match &atom.value().relation {
                    RelationRef::Declared(name) => self.cell.rules.iter().position(|(rule, _)| *rule == name).map(CellRead::Rule),
                    RelationRef::Output(output) if self.is_init_output(output).is_some() => Some(CellRead::Init),
                    _ => None,
                };
                reads.extend(read);
            });
        }
        reads
    }

    /// The port of the `INIT` form's output that `output` reads, where it
    /// reads one.
    fn is_init_output<'o>(&self, output: &'o crate::program::OutputName) -> Option<&'o PortName> {
        let init = self.cell.init?;
        match (&output.of, &output.path[..]) {
            (OutputOwner::Instance(instance), [OutputStep::Port(port)]) if *instance == init.name => Some(port),
            _ => None,
        }
    }

    /// The type of each column of `form`, `None` at a column with a fault.
    /// `what` names a column, for a diagnostic.
    fn column_types(&self, form: &CellForm<'_>, what: &dyn Fn(&ColumnName) -> String) -> Vec<Option<SiteType>> {
        form.columns
            .iter()
            .map(|(column, label)| match self.label_type(&[form.body], *label) {
                Ok(ty) => Some(ty),
                Err(message) => {
                    self.fault(CheckId::Types, format!("the label of {} {message}", what(column)));
                    None
                }
            })
            .collect()
    }

    /// The type that the sites of `label` in `bodies` give it, or the text
    /// of its fault: the meet of its fixed types, as [`label_type`] gives it
    /// over each body, or the one type parameter of the cell instance its
    /// sites give where they give no fixed type.
    fn label_type(&self, bodies: &[&Body], label: LabelId) -> Result<SiteType, String> {
        let parameters: RefCell<Vec<TypeParameter>> = RefCell::new(Vec::new());
        let fixed_site = Cell::new(false);
        let site = |atom: &Atom, path: &[ColumnName]| match self.site_type(atom, path) {
            Some(SiteType::Fixed(ty)) => {
                fixed_site.set(true);
                Some(ty)
            }
            Some(SiteType::Parameter(parameter)) => {
                let mut parameters = parameters.borrow_mut();
                if !parameters.contains(&parameter) {
                    parameters.push(parameter);
                }
                None
            }
            None => None,
        };
        let mut fixed: Option<ValueType> = None;
        for body in bodies {
            let ty = label_type(body, label, &site).map_err(label_fault_message)?;
            fixed = match (fixed, ty) {
                (Some(a), Some(b)) => match a.meet(&b) {
                    Meet::Type(ty) => Some(ty),
                    Meet::Empty => return Err(label_fault_message(LabelFault::EmptyMeet(a, b))),
                },
                (a, b) => a.or(b),
            };
        }
        let parameters = parameters.into_inner();
        match (&parameters[..], fixed) {
            ([], Some(ty)) => Ok(SiteType::Fixed(ty)),
            ([], None) => Err("stands at no site that gives a type".to_string()),
            ([parameter], _) if !fixed_site.get() => Ok(SiteType::Parameter(parameter.clone())),
            ([parameter], _) => Err(format!("stands at sites of the type parameter `{}` and at sites of a fixed type", parameter.0)),
            (parameters, _) => {
                let names: Vec<String> = parameters.iter().map(|p| format!("`{}`", p.0)).collect();
                Err(format!("stands at sites of the type parameters {}", names.join(", ")))
            }
        }
    }

    /// The type that the column `path` gives of the relation `atom` reads:
    /// a lib name's, as [`MacroDerivation`] gives it, a column of the cell
    /// instance's own input, a `RULE` form's column, or a column of an
    /// output of the `INIT` form under its binding. A read of a form being
    /// typed gives no type.
    fn site_type(&self, atom: &Atom, path: &[ColumnName]) -> Option<SiteType> {
        let column = path.first()?;
        match &atom.relation {
            RelationRef::Lib(_) => self.macros.site_type(atom, path).map(SiteType::Fixed),
            RelationRef::Fact(_) => None,
            RelationRef::DefinedPort(port) => {
                let input = self.cell.inputs.iter().find(|input| input.port.name == *port)?;
                SiteType::of_column(&input.port.columns.iter().find(|c| c.name == *column)?.ty)
            }
            RelationRef::Declared(name) => {
                let i = self.cell.rules.iter().position(|(rule, _)| *rule == name)?;
                let FormState::Typed(types) = &self.rules[i] else { return None };
                let index = self.cell.rules[i].1.columns.iter().position(|(c, _)| c == column)?;
                types[index].clone()
            }
            RelationRef::Output(output) => match self.init_column(output, column)? {
                InitColumn::Type(ty) => Some(ty),
                InitColumn::Record(_, fields) => record_field(fields, path.get(1)?).cloned(),
            },
        }
    }

    /// What the `INIT` form's binding gives the column `column` of the
    /// output `output` reads, where `output` is an output of the `INIT`
    /// form and the form is typed.
    fn init_column(&self, output: &crate::program::OutputName, column: &ColumnName) -> Option<InitColumn<'_>> {
        let port = self.is_init_output(output)?;
        let FormState::Typed(bindings) = &self.init else { return None };
        let outputs = self.construction?.outputs;
        let ty = &outputs.iter().find(|p| p.name == *port)?.columns.iter().find(|c| c.name == *column)?.ty;
        let ColumnType::Parameter(parameter) = ty else { return SiteType::of_column(ty).map(InitColumn::Type) };
        match &bindings.iter().find(|(p, _)| p == parameter)?.1 {
            Binding::One(ty) => Some(InitColumn::Type(ty.clone())),
            Binding::Record(fields) => Some(InitColumn::Record(parameter, fields)),
        }
    }

    /// Gives a fault for each field that a site on an output of the `INIT`
    /// form names, in any body of the cell instance, where the record bound
    /// to the site's column has no such field. It reads the direct
    /// arguments of each site, so a field that holds sites gives one fault.
    fn check_fields(&self) {
        use crate::program::SiteArg;
        let outputs = self.cell.outputs.iter().map(|(_, form)| form.body);
        let rules = self.cell.rules.iter().map(|(_, form)| form.body);
        let bodies: Vec<&Body> = outputs.chain(rules).chain(self.bodies_of(CellRead::Init)).collect();
        for body in bodies {
            each_conjunct(body, &mut |conjunct| {
                let (Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom))) = conjunct else { return };
                let atom = atom.value();
                let RelationRef::Output(output) = &atom.relation else { return };
                for site in atom.sites.iter() {
                    let Some(InitColumn::Record(parameter, fields)) = self.init_column(output, &site.column) else { continue };
                    for arg in site.value.args.iter() {
                        let field = match arg {
                            SiteArg::Field(field) => &field.column,
                            SiteArg::NamedLabel { name, .. } => name,
                            SiteArg::Label(_) => continue,
                        };
                        if record_field(fields, field).is_none() {
                            let message = format!(
                                "a site on `{}` of `{}` names the field `{}`, which the record bound to `{}` does not have",
                                column_display(&site.column),
                                crate::write::relation_ref(&atom.relation),
                                column_display(field),
                                parameter.0
                            );
                            self.fault(CheckId::SiteColumns, message);
                        }
                    }
                }
            });
        }
    }

    /// The binding of each type parameter of the underlying construction by
    /// the `INIT` form: the key clause binds the parameter of the `key`
    /// column to a record of its `^` labels, then the first projection onto
    /// each other parameter, in the order of the form, binds it
    /// (`docs/arclog/arclog.md#instance`). An `INIT` with no key clause
    /// whose inputs project nothing onto the `key` column binds it to
    /// `Unit`.
    fn bind(&self) -> Box<[(TypeParameter, Binding)]> {
        let (Some(init), Some(construction)) = (self.cell.init, self.construction) else { return Box::default() };
        let key_parameter = construction.inputs.iter().find_map(|input| {
            let column = input.port.columns.iter().find(|c| c.name == ColumnName::Written(KEY_COLUMN.into()))?;
            match &column.ty {
                ColumnType::Parameter(parameter) => Some(parameter.clone()),
                _ => None,
            }
        });
        let mut bindings: Vec<(TypeParameter, Binding)> = Vec::new();
        let mut inputs: Vec<(&crate::program::InstanceInput, Option<&Body>)> = Vec::new();
        if let Some(key) = &init.key {
            let key = key.value();
            let key_body = key.key.body.value();
            match &key_parameter {
                Some(parameter) => {
                    let fields = key.key.columns.iter().filter_map(|column| {
                        let ty = self.head_label_type(&[key_body], column.label, &column.name)?;
                        Some((field_name(&column.name), ty))
                    });
                    bindings.push((parameter.clone(), Binding::Record(fields.collect())));
                }
                None => self.fault(CheckId::Types, format!("the `INIT` form has a key clause, and `{}` has no `key` column", init.component.0)),
            }
            inputs.extend(key.inputs.iter().map(|input| (input.value(), Some(key_body))));
        }
        inputs.extend(init.inputs.iter().map(|input| (input.value(), None)));
        for (input, key_body) in inputs {
            let Some(port) = construction.inputs.iter().find(|i| i.port.name == input.name) else {
                self.fault(CheckId::Scope, format!("the `INIT` form gives the input `{}`, which `{}` has no input of", input.name.0, init.component.0));
                continue;
            };
            let bodies: Vec<&Body> = std::iter::once(input.body.value()).chain(key_body).collect();
            for site in input.head.iter() {
                let Some(column) = port.port.columns.iter().find(|c| c.name == site.column) else { continue };
                let ColumnType::Parameter(parameter) = &column.ty else { continue };
                if bindings.iter().any(|(p, _)| p == parameter) {
                    continue;
                }
                if let Some(binding) = self.projection(&bodies, site) {
                    bindings.push((parameter.clone(), binding));
                }
            }
        }
        for parameter in construction.type_parameters {
            if bindings.iter().any(|(p, _)| p == parameter) {
                continue;
            }
            if init.key.is_none() && key_parameter.as_ref() == Some(parameter) {
                bindings.push((parameter.clone(), Binding::One(SiteType::Fixed(ValueType::Unit))));
                continue;
            }
            self.fault(CheckId::Types, format!("the `INIT` form binds the type parameter `{}` of `{}` to no type", parameter.0, init.component.0));
        }
        bindings.into()
    }

    /// The binding that the head site `site` of an input gives its column's
    /// type parameter: the type of its one label, or a record with a field
    /// for each of its sites, named by the site's head or by its label where
    /// it is elided.
    fn projection(&self, bodies: &[&Body], site: &crate::program::Site) -> Option<Binding> {
        use crate::program::SiteArg;
        let args = &site.value.args[..];
        if let [arg @ (SiteArg::Label(_) | SiteArg::NamedLabel { .. })] = args {
            let label = arg.label().and_then(use_label)?;
            return self.head_label_type(bodies, label, &site.column).map(Binding::One);
        }
        let mut fields = Vec::new();
        for arg in args {
            let (name, label) = match arg {
                SiteArg::NamedLabel { name, label } => (name, *label),
                SiteArg::Field(field) => match &field.value.args[..] {
                    [arg] if arg.label().is_some() => (&field.column, arg.label().expect("the argument is a label")),
                    _ => {
                        self.fault(CheckId::Grammar, format!("a head site on the field `{}` holds one label", column_display(&field.column)));
                        return None;
                    }
                },
                SiteArg::Label(_) => {
                    self.fault(CheckId::Grammar, format!("a head site on `{}` names each field of its record", column_display(&site.column)));
                    return None;
                }
            };
            let label = use_label(label)?;
            fields.push((field_name(name), self.head_label_type(bodies, label, name)?));
        }
        Some(Binding::Record(fields.into()))
    }

    /// The type of the label `label` of a head site or a key column, which
    /// stands for `column`, or `None` with its fault.
    fn head_label_type(&self, bodies: &[&Body], label: LabelId, column: &ColumnName) -> Option<SiteType> {
        match self.label_type(bodies, label) {
            Ok(ty) => Some(ty),
            Err(message) => {
                self.fault(CheckId::Types, format!("the label at `{}` of the `INIT` form {message}", column_display(column)));
                None
            }
        }
    }
}

/// The name of a construction's key column, which the key clause binds.
const KEY_COLUMN: &str = "key";

/// The type of the field `field` of the record `fields`, where it has one.
fn record_field<'f>(fields: &'f [(FieldName, SiteType)], field: &ColumnName) -> Option<&'f SiteType> {
    fields.iter().find(|(name, _)| ColumnName::Written(name.0.clone()) == *field).map(|(_, ty)| ty)
}

/// The field that a site's head or an elided site's label names.
fn field_name(column: &ColumnName) -> FieldName {
    match column {
        ColumnName::Written(name) => FieldName(name.clone()),
        ColumnName::Slot(_) => unreachable!("the reader of the registry file gives each column its written name"),
    }
}

/// Where [`cell_ports`] stands in its read of one cell instance.
#[derive(Clone, Debug)]
enum CellState {
    Unread,
    /// The cell instance its `INIT` form instantiates is being read, so a
    /// read of it now closes a cycle.
    Reading,
    Declared(Box<[Port]>),
    /// It has a fault, or instantiates a cell instance with one.
    Faulted,
}

/// The output ports of each cell instance of `cells` that has no fault,
/// with a diagnostic in `diagnostics` for each fault, as
/// [`super::macro_column_types`] gives them. A cell instance whose `INIT`
/// form instantiates another is read after it.
pub(super) fn cell_ports(
    macros: &MacroDerivation<'_, '_>,
    cells: &[CellMacro<'_>],
    components: &StableHashMap<LibName, Component>,
    diagnostics: &mut Vec<crate::diagnostic::Diagnostic>,
) -> StableHashMap<LibName, Box<[Port]>> {
    let mut states = vec![CellState::Unread; cells.len()];
    let mut stack = Vec::new();
    for i in 0..cells.len() {
        read_cell(i, macros, cells, components, &mut states, &mut stack, diagnostics);
    }
    let declared = states.into_iter().zip(cells).filter_map(|(state, cell)| match state {
        CellState::Declared(ports) => Some((cell.name.clone(), ports)),
        _ => None,
    });
    declared.collect()
}

/// Reads cell instance `i` after the cell instance its `INIT` form
/// instantiates, where it instantiates one, and sets its state.
fn read_cell(
    i: usize,
    macros: &MacroDerivation<'_, '_>,
    cells: &[CellMacro<'_>],
    components: &StableHashMap<LibName, Component>,
    states: &mut Vec<CellState>,
    stack: &mut Vec<usize>,
    diagnostics: &mut Vec<crate::diagnostic::Diagnostic>,
) {
    match states[i] {
        CellState::Unread => {}
        CellState::Reading => {
            let start = stack.iter().position(|&j| j == i).expect("a cell instance being read stands on the stack");
            let names: Vec<String> = stack[start..].iter().map(|&j| format!("`{}`", cells[j].name.0)).collect();
            for &j in &stack[start..] {
                let message = format!("the cell instance `{}` instantiates itself through the cell instances {}", cells[j].name.0, names.join(", "));
                diagnostics.push(crate::read::check_error(CheckId::Cycles, message, cells[j].place));
                states[j] = CellState::Faulted;
            }
            return;
        }
        CellState::Declared(_) | CellState::Faulted => return,
    }
    let cell = &cells[i];
    let component = cell.init.map(|init| &init.component);
    let underlying = component.and_then(|name| cells.iter().position(|c| c.name == name));
    states[i] = CellState::Reading;
    stack.push(i);
    if let Some(j) = underlying {
        read_cell(j, macros, cells, components, states, stack, diagnostics);
    }
    stack.pop();
    if matches!(states[i], CellState::Faulted) {
        return;
    }
    let construction = match (component, underlying) {
        (_, Some(j)) => match &states[j] {
            CellState::Declared(outputs) => {
                Some(Construction { type_parameters: cells[j].type_parameters, inputs: cells[j].inputs, outputs })
            }
            _ => {
                states[i] = CellState::Faulted;
                return;
            }
        },
        (Some(name), None) => match components.get(name) {
            Some(c) => Some(Construction { type_parameters: &c.type_parameters, inputs: &c.inputs, outputs: &c.outputs }),
            None => {
                let message = format!("the `INIT` form of the cell instance `{}` instantiates `{}`, which is no component", cell.name.0, name.0);
                diagnostics.push(crate::read::check_error(CheckId::Scope, message, cell.place));
                states[i] = CellState::Faulted;
                return;
            }
        },
        (None, None) => None,
    };
    let ports = CellDerivation::ports(macros, cell, construction, diagnostics);
    states[i] = match ports {
        Some(ports) => CellState::Declared(ports),
        None => CellState::Faulted,
    };
}
