//! The reader of the registry file's two macro forms: a relation macro,
//! `(macro <name> (columns ...) <body>)`, and a cell instance,
//! `(macro <name> (component ...) ...)`, with the labels of their bodies that
//! their columns stand for.

use super::reader::{headed, BodyInFile, FileReader, WrittenCell, WrittenMacro, LabelColumns, COLUMNS, COMPONENT, OUTPUT};
use super::*;

impl FileReader {
    /// `(macro <name> (columns ...) <body>)` or a cell instance,
    /// `(macro <name> (component ...) ...)`, after its head.
    pub(super) fn macro_form(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the macro's name", place)?.into());
        match rest.get(1).and_then(head_of) {
            Some(COLUMNS) => self.relation_macro(name, rest, place),
            Some(COMPONENT) => self.cell_instance(name, rest, place),
            _ => self.refuse(format!("a macro's name stands before its `({COLUMNS} ...)` or its `({COMPONENT} ...)` form"), place),
        }
    }

    /// The label of `labels` named `name`, the first that stands, or a fault
    /// that `what` stands for no label the body keeps.
    pub(super) fn label_of(&mut self, labels: &crate::read::LabelNames, name: &str, what: &str, place: SourcePlace) -> Option<LabelId> {
        match labels.iter().find(|(n, _)| &**n == name) {
            Some((_, label)) => Some(*label),
            None => {
                self.fault(CheckId::Scope, format!("{what} stands for the label `{name}`, which its body does not keep"), place);
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
            let (body, kept) = self.read(read_body(&rule[1..], init))?;
            let columns = kept.iter().map(|(n, label)| (ColumnName::Written(n.clone()), *label)).collect();
            bodies.push(body.clone());
            rules.push(CellRule { name: rule_name, body, columns });
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
}
