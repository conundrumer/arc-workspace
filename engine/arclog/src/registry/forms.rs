//! The reader of the registry file's forms other than its macro forms:
//! `relation`, `component`, `proposer`, `constants`, `type` and
//! `fact`, with the columns and the types they write, and the `frames` forms
//! of a relation, a macro and an output.

use super::reader::*;
use super::records::{ArclogProposer, ComponentHead};
use super::spellings::*;
use crate::program::column_spelled;
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
            Some(TYPE) => self.type_form(rest, place),
            Some(FACT) => self.fact(rest, place),
            Some(MACRO) => self.macro_form(rest, place),
            Some(REFINES) => match rest.first() {
                Some(SExpr::Symbol { text, .. }) => {
                    self.refines.insert(text.to_string().into_boxed_str(), rest[1..].to_vec().into_boxed_slice());
                    Some(())
                }
                _ => self.refuse("a `refines` form names a lib element", place),
            },
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
            _ => match parameters.iter().find(|p| &*p.name == text) {
                Some(parameter) => Some((ColumnType::Parameter(parameter.clone()), None)),
                None => self.refuse(format!("`{text}` is no type and no type parameter of the component"), expr.place()),
            },
        }
    }

    /// The type that `expr`, a type name, writes. `what` names the type.
    pub(super) fn value_type(&mut self, expr: &SExpr, what: &str) -> Option<ValueType> {
        let text = self.symbol(Some(expr), what, expr.place())?;
        match spelling::parse(spelling::TYPE_NAMES, text) {
            Some(name) => Some(name.value_type()),
            None => self.refuse(format!("`{text}` is no type name"), expr.place()),
        }
    }

    /// The type parameter that `expr`, `<name>` or `(<name> <type>)`, writes.
    fn type_parameter(&mut self, expr: &SExpr, at: SourcePlace) -> Option<TypeParameter> {
        let SExpr::List { items, .. } = expr else {
            let name = self.symbol(Some(expr), "a type parameter", at)?;
            return Some(TypeParameter { name: name.into(), bound: None });
        };
        let [name, bound] = &items[..] else {
            return self.refuse("a type parameter is a name or a list of its name and its bound", expr.place());
        };
        let name = self.symbol(Some(name), "the type parameter's name", at)?;
        let bound = self.value_type(bound, "a type parameter's bound")?;
        Some(TypeParameter { name: name.into(), bound: Some(bound) })
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

    /// `(relation <name> (columns ...) [(modes ...)] [(frames ...)] [(types ...)])`, after its head.
    fn relation(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let name = LibName(self.symbol(rest.first(), "the relation's name", place)?.into());
        let columns = self.columns(rest.get(1), COLUMNS, &[], place)?;
        let mut at = 2;
        let modes = match rest.get(at).filter(|expr| headed(expr, MODES).is_some()) {
            Some(expr) => {
                at += 1;
                let names: Vec<ColumnName> = columns.iter().map(|c| c.name.clone()).collect();
                self.modes(expr, &names, place)?
            }
            None => Box::default(),
        };
        let frames = match rest.get(at).and_then(|expr| headed(expr, FRAMES)) {
            Some(items) => {
                at += 1;
                self.relation_frames(items, &columns, &format!("the relation `{}`", name.0))?
            }
            None => Box::default(),
        };
        let rules = match rest.get(at).and_then(|expr| headed(expr, TYPES)) {
            Some(items) => {
                at += 1;
                self.type_rules(items)?
            }
            None => Box::default(),
        };
        self.no_more(rest.get(at..).unwrap_or_default())?;
        if self.declare(&name, place) {
            self.entries.insert(name, LibEntry::Relation(AlgebraRelation { columns, modes, frames, rules }));
        }
        Some(())
    }

    /// The rules that `items`, the items of a `(frames ...)` form of a relation or a
    /// macro named by `what`, write for its `columns`, each rule naming columns of them.
    pub(super) fn relation_frames(&mut self, items: &[SExpr], columns: &[Column], what: &str) -> Option<Box<[(ColumnName, FrameRule)]>> {
        let refer = |text: &str| columns.iter().find(|own| own.name == ColumnName::Written(text.into())).map(|own| FrameColumn { input: None, column: own.name.clone() });
        self.frame_rules(items, columns, &[], what, &refer)
    }

    /// The rules that `items`, the items of a `(frames ...)` form of the output
    /// `what` with `columns`, write, each rule naming `<input>.<column>` of
    /// the component's `inputs`; `mapped` are the columns a `copies` row maps.
    fn output_frames(&mut self, items: &[SExpr], columns: &[Column], mapped: &[ColumnName], inputs: &[InputPort], what: &str) -> Option<Box<[(ColumnName, FrameRule)]>> {
        let refer = |text: &str| {
            let (input, column) = text.split_once('.')?;
            let input = inputs.iter().find(|own| &*own.port.name.0 == input)?;
            let column = input.port.columns.iter().find(|own| own.name == ColumnName::Written(column.into()))?;
            Some(FrameColumn { input: Some(input.port.name.clone()), column: column.name.clone() })
        };
        self.frame_rules(items, columns, mapped, what, &refer)
    }

    /// The rules that `items`, the items of a `(frames (<column> <rule>) ...)`
    /// form, write for columns of `columns`, which `what` names: each column
    /// once, of type `Position` or `Box`, and none of `mapped`. `refer` gives the
    /// column that a name in a rule's `(of ...)` stands for.
    fn frame_rules(&mut self, items: &[SExpr], columns: &[Column], mapped: &[ColumnName], what: &str, refer: &dyn Fn(&str) -> Option<FrameColumn>) -> Option<Box<[(ColumnName, FrameRule)]>> {
        let mut rules: Vec<(ColumnName, FrameRule)> = Vec::new();
        for item in items {
            let SExpr::List { items: pair, .. } = item else {
                return self.refuse("a rule of a `frames` form is a list of a column and its rule", item.place());
            };
            let [column, rule] = &pair[..] else {
                return self.refuse("a rule of a `frames` form is a list of a column and its rule", item.place());
            };
            let text = self.symbol(Some(column), "the rule's column", item.place())?;
            let name = ColumnName::Written(text.into());
            let Some(own) = columns.iter().find(|own| own.name == name) else {
                return self.refuse(format!("`{text}` is no column of {what}"), column.place());
            };
            let rule = self.frame_rule(rule, what, refer)?;
            if let Some(by) = rule.size.as_ref().and_then(|size| size.by.as_ref()) {
                if by.input.is_some() {
                    return self.refuse(format!("the `{NEW}` rule of the column `{text}` of {what} takes no `({BY} <column>)` form: a rule of a component's output names no element"), item.place());
                }
                if columns.iter().find(|own| own.name == by.column).and_then(|own| own.ty.fixed()) != Some(&ValueType::D4) {
                    return self.refuse(format!("the `({BY} <column>)` form of the `{NEW}` rule of the column `{text}` of {what} names a column of type `D4`"), item.place());
                }
            }
            match (own.ty.fixed(), &rule.size) {
                (Some(ValueType::Box), None) if rule.makes => {
                    return self.refuse(format!("the `{NEW}` rule of the column `{text}` of {what}, of type `Box`, names the column whose values have the made values' own size, in a `({SIZE} <column>)` form"), item.place());
                }
                (Some(ValueType::Position), Some(_)) => {
                    return self.refuse(format!("the `{NEW}` rule of the column `{text}` of {what}, of type `Position`, takes no `({SIZE} <column>)` form: a Position's margins give its frame's extent"), item.place());
                }
                _ => {}
            }
            if !own.has_frame() {
                self.fault(CheckId::Scope, format!("the column `{text}` of {what} is no `Position` or `Box`, so a rule gives it no frame"), item.place());
                continue;
            }
            if mapped.contains(&name) {
                self.fault(CheckId::Scope, format!("the column `{text}` of {what} is mapped by a `copies` row, so it has the frame of the column it copies and takes no rule"), item.place());
                continue;
            }
            let earlier: Vec<String> = rules.iter().map(|(column, _)| column_spelled(column)).collect();
            if self.named_once(earlier.iter().map(String::as_str), text, &format!("a `frames` form of {what}"), item.place()) {
                rules.push((name, rule));
            }
        }
        Some(rules.into())
    }

    /// The rule that `expr` writes: `new`, `(of <column> ...)`, or `(new [(of <column> ...)] [(size <column> [(by <column>)])])`.
    fn frame_rule(&mut self, expr: &SExpr, what: &str, refer: &dyn Fn(&str) -> Option<FrameColumn>) -> Option<FrameRule> {
        if matches!(expr, SExpr::Symbol { text, .. } if &**text == NEW) {
            return Some(FrameRule { makes: true, of: Box::default(), size: None });
        }
        if let Some(named) = headed(expr, OF) {
            return Some(FrameRule { makes: false, of: self.frame_columns(named, expr.place(), what, refer)?, size: None });
        }
        if let Some(items) = headed(expr, NEW)
            && !items.is_empty()
        {
            let (of, rest) = match items.first().and_then(|item| headed(item, OF).map(|named| (item, named))) {
                Some((item, named)) => (self.frame_columns(named, item.place(), what, refer)?, &items[1..]),
                None => (Box::default(), items),
            };
            let size = match rest {
                [] => None,
                [item] => Some(self.frame_size_form(item, what, refer)?),
                [_, extra, ..] => return self.refuse(format!("a `{NEW}` rule ends in its `({SIZE} <column> [({BY} <column>)])` form"), extra.place()),
            };
            return Some(FrameRule { makes: true, of, size });
        }
        self.refuse(format!("a rule is `{NEW}`, `({OF} <column> ...)` or `({NEW} [({OF} <column> ...)] [({SIZE} <column> [({BY} <column>)])])`"), expr.place())
    }

    /// The `(size <column> [(by <column>)])` form that `item` writes.
    fn frame_size_form(&mut self, item: &SExpr, what: &str, refer: &dyn Fn(&str) -> Option<FrameColumn>) -> Option<FrameSize> {
        let (column, by) = match headed(item, SIZE) {
            Some([column]) => (column, None),
            Some([column, by]) => match headed(by, BY) {
                Some([element]) => (column, Some(element)),
                _ => return self.refuse(format!("the second part of a `({SIZE} ...)` form is a `({BY} <column>)` form"), by.place()),
            },
            _ => return self.refuse(format!("a `({SIZE} <column> [({BY} <column>)])` form names a column and, after it, may have a `({BY} <column>)` form"), item.place()),
        };
        let column = self.frame_column(column, item.place(), what, refer)?;
        let by = match by {
            Some(element) => Some(self.frame_column(element, item.place(), what, refer)?),
            None => None,
        };
        Some(FrameSize { column, by })
    }

    /// The column that `item`, the column a rule names, stands for.
    fn frame_column(&mut self, item: &SExpr, place: SourcePlace, what: &str, refer: &dyn Fn(&str) -> Option<FrameColumn>) -> Option<FrameColumn> {
        Some(self.frame_columns(std::slice::from_ref(item), place, what, refer)?[0].clone())
    }

    /// The columns that `items`, the items of an `(of ...)` form, name, at least one.
    fn frame_columns(&mut self, items: &[SExpr], place: SourcePlace, what: &str, refer: &dyn Fn(&str) -> Option<FrameColumn>) -> Option<Box<[FrameColumn]>> {
        if items.is_empty() {
            return self.refuse(format!("an `({OF} ...)` form names a column"), place);
        }
        let mut named = Vec::new();
        for item in items {
            let text = self.symbol(Some(item), "a column a rule names", place)?;
            let Some(column) = refer(text) else {
                return self.refuse(format!("`{text}` is no column that a rule of {what} can name"), item.place());
            };
            named.push(column);
        }
        Some(named.into())
    }

    /// `(modes (<Column> ...) ...)`, each mode a nonempty list of the columns
    /// `columns`.
    pub(super) fn modes(&mut self, expr: &SExpr, columns: &[ColumnName], place: SourcePlace) -> Option<Box<[Mode]>> {
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
                if !columns.contains(&column) {
                    return self.refuse(format!("`{text}` is no column of the form"), name.place());
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
        let parameters: Option<Vec<TypeParameter>> = parameters.iter().map(|p| self.type_parameter(p, place)).collect();
        let type_parameters: Box<[TypeParameter]> = parameters?.into();
        let inputs = self.headed(rest.get(3), INPUTS, place)?;
        let inputs: Option<Vec<InputPort>> = inputs.iter().map(|input| self.input(input, &type_parameters)).collect();
        let inputs = inputs?;
        if inputs.iter().filter(|input| input.need == Some(Need::OneOf)).count() == 1 {
            return self.refuse(format!("the component marks one input `{ONE_OF}`: its inputs so marked are a group of two or more, and one input that the component needs alone is marked `{REQUIRED}`"), place);
        }
        let outputs = self.headed(rest.get(4), OUTPUTS, place)?;
        self.no_more(rest.get(5..).unwrap_or_default())?;
        Some(ComponentHead { name, kind, type_parameters, inputs: inputs.into(), outputs })
    }

    /// `(component <Name> <kind> (type-parameters ...) (inputs ...) (outputs ...))`,
    /// after its head, each output column with its type.
    fn component(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<(LibName, Component)> {
        let head = self.component_head(rest, place)?;
        let outputs: Option<Vec<Port>> = head.outputs.iter().map(|output| self.output(output, &head.type_parameters, &head.inputs)).collect();
        let component = Component { kind: head.kind, type_parameters: head.type_parameters, inputs: head.inputs, outputs: outputs?.into() };
        Some((head.name, component))
    }

    /// An output, `(<output> (<column> <type>) ... [(copies <row> ...)])`, whose
    /// `copies` form reads the `inputs` of its component.
    fn output(&mut self, expr: &SExpr, parameters: &[TypeParameter], inputs: &[InputPort]) -> Option<Port> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("a port is a list of its name and its columns", expr.place());
        };
        let name = PortName(self.symbol(items.first(), "the port's name", *place)?.into());
        let mut rest = &items[1..];
        let frames = rest.last().and_then(|last| headed(last, FRAMES));
        if frames.is_some() {
            rest = &rest[..rest.len() - 1];
        }
        let copies = rest.last().and_then(|last| headed(last, COPIES));
        if copies.is_some() {
            rest = &rest[..rest.len() - 1];
        }
        let columns: Option<Vec<Column>> = rest.iter().map(|item| self.column(item, parameters).map(|(c, _)| c)).collect();
        let columns: Box<[Column]> = columns?.into();
        let copies = self.copied_rows(copies.unwrap_or_default(), inputs, &name, &columns)?;
        let mapped: Vec<ColumnName> = copies.iter().flat_map(|row| row.alternatives.iter()).flat_map(|from| from.columns.iter()).map(|&(_, output)| columns[output].name.clone()).collect();
        let frames = self.output_frames(frames.unwrap_or_default(), &columns, &mapped, inputs, &format!("the output `{}`", name.0))?;
        Some(Port { name, columns, copies, frames })
    }

    /// The declared rows that `rows`, the items of a `(copies ...)` form of the output
    /// `name` with `columns`, write.
    fn copied_rows(&mut self, rows: &[SExpr], inputs: &[InputPort], name: &PortName, columns: &[Column]) -> Option<Box<[CopiedRow]>> {
        let mut copies = Vec::new();
        for row in rows {
            let alternatives = match headed(row, EITHER) {
                Some(alternatives) if !alternatives.is_empty() => alternatives,
                Some(_) => return self.refuse(format!("an `({EITHER} ...)` row holds an alternative"), row.place()),
                None => std::slice::from_ref(row),
            };
            let alternatives: Option<Vec<CopiedFrom>> = alternatives.iter().map(|alternative| self.copied_from(alternative, inputs, columns)).collect();
            let alternatives: Box<[CopiedFrom]> = alternatives?.into();
            let mapped = |from: &CopiedFrom| {
                let mut outputs: Vec<usize> = from.columns.iter().map(|&(_, output)| output).collect();
                outputs.sort_unstable();
                outputs
            };
            if alternatives.iter().any(|from| mapped(from) != mapped(&alternatives[0])) {
                return self.refuse(format!("the alternatives of a row of `{}` map different output columns", name.0), row.place());
            }
            copies.push(CopiedRow { alternatives });
        }
        Some(copies.into())
    }

    /// An alternative of a declared row, `(<input> (<input column> <output column>) ...)`:
    /// the input and the columns of the output `columns` it copies, none of them a `key`
    /// column, each output column once, and each pair of one type.
    fn copied_from(&mut self, expr: &SExpr, inputs: &[InputPort], columns: &[Column]) -> Option<CopiedFrom> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("a declared row is a list of an input and its column pairs", expr.place());
        };
        let name = self.symbol(items.first(), "the declared row's input", *place)?;
        let Some(input) = inputs.iter().position(|input| &*input.port.name.0 == name) else {
            return self.refuse(format!("`{name}` is no input of the component"), items[0].place());
        };
        let own = &inputs[input].port.columns;
        let mut pairs: Vec<(usize, usize)> = Vec::new();
        for item in &items[1..] {
            let SExpr::List { items: names, place, .. } = item else {
                return self.refuse("a column pair is a list of an input column and an output column", item.place());
            };
            let [from, to] = &names[..] else {
                return self.refuse("a column pair is a list of an input column and an output column", *place);
            };
            let from_name = self.symbol(Some(from), "a pair's input column", *place)?;
            let to_name = self.symbol(Some(to), "a pair's output column", *place)?;
            let at = |columns: &[Column], name: &str| columns.iter().position(|column| matches!(&column.name, ColumnName::Written(written) if &**written == name));
            let Some(from_at) = at(own, from_name) else {
                return self.refuse(format!("`{from_name}` is no column of the input `{name}`"), from.place());
            };
            let Some(to_at) = at(columns, to_name) else {
                return self.refuse(format!("`{to_name}` is no column of the output"), to.place());
            };
            if is_key(&own[from_at]) || is_key(&columns[to_at]) {
                return self.refuse("a `key` column is copied by the group's key, and a pair names none", item.place());
            }
            if pairs.iter().any(|&(_, output)| output == to_at) {
                return self.refuse(format!("the row names the output column `{to_name}` twice"), item.place());
            }
            if own[from_at].ty != columns[to_at].ty {
                return self.refuse(format!("the input column `{from_name}` and the output column `{to_name}` have different types"), item.place());
            }
            pairs.push((from_at, to_at));
        }
        Some(CopiedFrom { input, columns: pairs.into() })
    }

    /// An input, `(<input> (<column> <type>) ... [(default <rows>)] [reads-outputs] [from-key] [required | one-of])`.
    fn input(&mut self, expr: &SExpr, parameters: &[TypeParameter]) -> Option<InputPort> {
        let SExpr::List { items, place, .. } = expr else {
            return self.refuse("an input is a list of its name and its columns", expr.place());
        };
        let name = PortName(self.symbol(items.first(), "the input's name", *place)?.into());
        let mut rest = &items[1..];
        let need = if take_mark(&mut rest, REQUIRED) {
            Some(Need::Required)
        } else if take_mark(&mut rest, ONE_OF) {
            Some(Need::OneOf)
        } else {
            None
        };
        if need.is_some() && (take_mark(&mut rest, REQUIRED) || take_mark(&mut rest, ONE_OF)) {
            return self.refuse(format!("an input takes one of the marks `{REQUIRED}` and `{ONE_OF}`, not both"), *place);
        }
        let from_key = take_mark(&mut rest, FROM_KEY);
        let reads_outputs = take_mark(&mut rest, READS_OUTPUTS);
        let default_rows = rest.last().and_then(|last| headed(last, DEFAULT));
        if default_rows.is_some() {
            if from_key {
                return self.refuse("an input with default rows takes no `from-key` mark", *place);
            }
            if need.is_some() {
                return self.refuse(format!("an input with default rows takes no `{REQUIRED}` or `{ONE_OF}` mark, since its default rows hold where the instance writes no clause for it"), *place);
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
        if need.is_some() && from_key && columns.iter().all(is_key) {
            return self.refuse(format!("an input marked `{FROM_KEY}` whose one column is `key` takes no `{REQUIRED}` or `{ONE_OF}` mark, since the key fills it where the instance writes no clause for it"), *place);
        }
        let default = match default_rows {
            Some(rows) => Some(DefaultRows { written: self.read(read_param_value(rows, &written))? }),
            None => None,
        };
        Some(InputPort { port: Port { name, columns: columns.into(), copies: Box::default(), frames: Box::default() }, default, reads_outputs, from_key, need })
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

    /// `(type <Name>)`, after its head.
    fn type_form(&mut self, rest: &[SExpr], place: SourcePlace) -> Option<()> {
        let text = self.symbol(rest.first(), "the type's name", place)?;
        let Some(name) = spelling::parse(spelling::TYPE_NAMES, text) else {
            return self.refuse(format!("`{text}` is no type name"), rest[0].place());
        };
        self.no_more(rest.get(1..).unwrap_or_default())?;
        if !self.types.insert(name) {
            return self.refuse(format!("the file has two `type` forms of `{text}`"), place);
        }
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
