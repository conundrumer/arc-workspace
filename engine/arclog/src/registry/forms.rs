//! The reader of the registry file's forms other than its macro forms:
//! `relation`, `component`, `proposer`, `constants` and
//! `fact`, with the columns and the types they write.

use super::reader::*;
use super::records::{ArclogProposer, ComponentHead};
use super::spellings::*;
use super::*;

impl FileReader {
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
            let mut bound = Vec::new();
            for name in names.iter() {
                let text = self.symbol(Some(name), "a mode's column", *place)?;
                let column = ColumnName::Written(text.into());
                if !columns.iter().any(|c| c.name == column) {
                    return self.refuse(format!("`{text}` is no column of the relation"), name.place());
                }
                bound.push(column);
            }
            modes.push(Mode { bound: bound.into() });
        }
        Some(modes.into())
    }

    /// `(component <Name> <kind> (type-parameters ...) (inputs ...) (outputs ...))`,
    /// after its head.
    pub(super) fn component_head<'e>(&mut self, rest: &'e [SExpr], place: SourcePlace) -> Option<ComponentHead<'e>> {
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

    /// An input, `(<input> (<column> <type>) ... [(default <rows>)] [reads-outputs] [explicit])`.
    fn input(&mut self, expr: &SExpr, parameters: &[TypeParameter]) -> Option<InputPort> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("an input is a list of its name and its columns", expr.place());
        };
        let name = PortName(self.symbol(items.first(), "the input's name", *place)?.into());
        let mut rest = &items[1..];
        let explicit = take_mark(&mut rest, EXPLICIT);
        let reads_outputs = take_mark(&mut rest, READS_OUTPUTS);
        let default_rows = rest.last().and_then(|last| headed(last, DEFAULT));
        if default_rows.is_some() {
            if explicit {
                return self.refuse("an input with default rows takes no `explicit` mark", *place);
            }
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
        Some(InputPort { port: Port { name, columns: columns.into() }, default, reads_outputs, explicit })
    }

    /// `(proposer <name> native [domain] (columns ...))` or
    /// `(proposer <name> arclog (columns <Label> ...))`,
    /// after its head.
    fn proposer(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the proposer's name", place)?.into());
        match self.symbol(rest.get(1), "the proposer's kind", place)? {
            NATIVE => {
                let domain = matches!(rest.get(2), Some(SExpr::Symbol { text, .. }) if &**text == DOMAIN);
                let at = 2 + usize::from(domain);
                let columns = self.columns(rest.get(at), COLUMNS, &[], place)?;
                self.no_more(rest.get(at + 1..).unwrap_or_default())?;
                if self.declare(&name, place) {
                    self.entries.insert(name, LibEntry::Proposer(Proposer { columns, kind: ProposerKind::Native { domain } }));
                }
            }
            ARCLOG => {
                let written = rest.get(2).and_then(|expr| headed(expr, COLUMNS));
                let columns = self.proposer_labels(written.unwrap_or_default(), &name, place)?;
                let after = if written.is_some() { 3 } else { 2 };
                self.no_more(rest.get(after..).unwrap_or_default())?;
                if self.declare(&name, place) {
                    self.arclog_proposers.push(ArclogProposer { name, place, columns });
                }
            }
            other => return self.refuse(format!("`{other}` is no kind of proposer, `{NATIVE}` or `{ARCLOG}`"), rest[1].place()),
        }
        Some(())
    }

    /// The labels that `items`, the items of the `(columns <Label> ...)` form
    /// of the arclog proposer `name`, write, each once. A form that names no label
    /// or names one label twice takes a fault, and the proposer still takes
    /// its clause, so the clause takes no fault of its own.
    fn proposer_labels(&mut self, items: &[SExpr], name: &LibName, place: SourcePlace) -> Option<Box<[Box<str>]>> {
        let mut labels: Vec<Box<str>> = Vec::new();
        let what = format!("the proposer `{}`", name.0);
        for item in items {
            let label = self.symbol(Some(item), "a column's label", place)?;
            if self.named_once(labels.iter().map(|l| &**l), label, &what, item.place()) {
                labels.push(label.into());
            }
        }
        if labels.is_empty() {
            self.fault(CheckId::Scope, format!("the proposer `{}` names no columns", name.0), place);
        }
        Some(labels.into())
    }

    /// Whether `column` is none of `earlier`, the columns that `what`, a
    /// form, names before it, or `false` with a fault that `what` names the
    /// column twice, at `place`.
    pub(super) fn named_once<'c>(&mut self, mut earlier: impl Iterator<Item = &'c str>, column: &str, what: &str, place: SourcePlace) -> bool {
        if earlier.any(|c| c == column) {
            self.fault(CheckId::Scope, format!("{what} names the column `{column}` twice"), place);
            return false;
        }
        true
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
}

/// Whether the last of `items` is the symbol `mark`, which it then drops
/// from `items`.
fn take_mark(items: &mut &[SExpr], mark: &str) -> bool {
    let marked = matches!(items.last(), Some(SExpr::Symbol { text, .. }) if &**text == mark);
    if marked {
        *items = &items[..items.len() - 1];
    }
    marked
}
