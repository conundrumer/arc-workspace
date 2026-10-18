//! The reader of the nodes of an arcdata file from its s-expressions, and of
//! one row of the registry file.
//!
//! Each node records its layout under its path, numbered as the arcdata
//! table of `engine/arclog/src/program/path.rs` gives, and the writer of
//! `engine/arclog/src/write/arcdata.rs` walks the nodes in the same order. A
//! node that the table gives no children records each token it writes,
//! those of its rows and grids among them.

use std::sync::Arc;

use crate::layout::SourcePlace;
use crate::program::path::NodePath;
use crate::program::*;
use crate::registry::LibName;

use super::arclog::{head_of, List, Reader, Record, R};
use super::spelling::{self as sp, parse};
use super::SExpr;

impl Reader {
    /// The arcdata file of `exprs`, whose end is `end`.
    pub(super) fn arcdata(&mut self, exprs: &[SExpr], end: SourcePlace) -> Node<Arcdata> {
        let root = NodePath::default();
        let mut representative = None;
        let mut params = Vec::new();
        let mut excludes = Vec::new();
        let mut records = Vec::new();
        let mut last = 0u8;
        let mut kept = 0u32;
        for expr in exprs {
            let path = root.child(kept);
            let read = self.optional(|r| {
                let form = r.top_form(expr, &path, &params)?;
                let rank = form.rank();
                if rank < last || (rank == 0 && kept > 0) {
                    return r.refuse("the form stands out of the order `docs/arclog/arcdata.md#arcdata` gives", expr.place());
                }
                Ok(form)
            });
            let Some(form) = read else { continue };
            last = form.rank();
            kept += 1;
            match form {
                Top::Representative(value) => representative = Some(value),
                Top::Param(value) => params.push(value),
                Top::Exclude(value) => excludes.push(value),
                Top::Record(value) => records.push(value),
            }
        }
        let mut record = Record::new(None);
        record.token(end);
        self.save(&root, record);
        Node::new(Arcdata {
            representative,
            params: params.into(),
            excludes: excludes.into(),
            witness_records: records.into(),
        })
    }

    /// The form of `expr`, where `params` are the `param` forms before it.
    fn top_form(&mut self, expr: &SExpr, path: &NodePath, params: &[Node<Param>]) -> R<Top> {
        let list = self.list(expr, "a form")?;
        let (head, place) = self.symbol(list.items.first(), "a form's keyword", list.place)?;
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        record.token(place);
        let form = match head {
            sp::REPRESENTATIVE => Top::Representative(self.representative(list.items, list.place, &mut record)?),
            sp::PARAM => Top::Param(Node::new(self.param(list.items, list.place, &mut record)?)),
            sp::EXCLUDE => Top::Exclude(self.exclude(list.items, list.place, &mut record)?),
            sp::ALTS_RECORD | sp::APPROXIMATED_RECORD => {
                Top::Record(self.witness_record(list.items, list.place, path, params, &mut record)?)
            }
            _ => return self.refuse(format!("`{head}` heads no form of an arcdata file"), place),
        };
        record.token(list.close);
        self.save(path, record);
        Ok(form)
    }

    fn representative(&mut self, items: &[SExpr], at: SourcePlace, record: &mut Record) -> R<Representative> {
        let (task_id, place) = self.symbol(items.get(1), "the representative's task id", at)?;
        record.token(place);
        let case = match items.get(2) {
            Some(expr) => Some(self.case_name(expr, record)?),
            None => None,
        };
        self.no_more(items, 3)?;
        Ok(Representative { task_id: task_id.into(), case })
    }

    /// A refusal at the item at `count` of `items`, where it has one.
    fn no_more(&mut self, items: &[SExpr], count: usize) -> R<()> {
        match items.get(count) {
            Some(extra) => self.refuse("the form holds no more items", extra.place()),
            None => Ok(()),
        }
    }

    /// One name, or a list of two or more names, each an alt's name.
    fn case_name(&mut self, expr: &SExpr, record: &mut Record) -> R<Arc<[AltsName]>> {
        Ok(self.name_group(expr, record)?.into_iter().map(|(text, _)| AltsName(text.into())).collect())
    }

    /// The names that `expr` writes: one symbol, or a list of two or more.
    fn name_group<'e>(&mut self, expr: &'e SExpr, record: &mut Record) -> R<Vec<(&'e str, SourcePlace)>> {
        if let SExpr::Symbol { text, place } = expr {
            record.token(*place);
            return Ok(vec![(text, *place)]);
        }
        let list = self.list(expr, "a name or a list of names")?;
        if list.items.len() < 2 {
            return self.refuse("a list of names holds two or more names", list.place);
        }
        record.token(list.open);
        let mut names = Vec::new();
        for item in list.items {
            let name = self.symbol(Some(item), "a name", list.place)?;
            record.token(name.1);
            names.push(name);
        }
        record.token(list.close);
        Ok(names)
    }

    fn param(&mut self, items: &[SExpr], at: SourcePlace, record: &mut Record) -> R<Param> {
        let (name, place) = self.symbol(items.get(1), "the parameter's name", at)?;
        let name = self.program_relation(name, place)?;
        record.token(place);
        let columns = self.columns(items.get(2), at, record)?;
        let value = self.param_value(&items[3..], &written_types(&columns), record)?;
        Ok(Param { name, columns, value })
    }

    fn columns(&mut self, expr: Option<&SExpr>, at: SourcePlace, record: &mut Record) -> R<Arc<[TypeName]>> {
        let Some(expr) = expr else { return self.refuse("the list lacks the parameter's column types", at) };
        let names = self.name_group(expr, record)?;
        names
            .into_iter()
            .map(|(text, place)| match parse(sp::TYPE_NAMES, text) {
                Some(ty) => Ok(ty),
                None => self.refuse(format!("`{text}` names no column type"), place),
            })
            .collect()
    }

    /// The rows of a `param` form or an `assign` form, all of one kind: rows
    /// of values, grids, or a derivation. `columns` gives the type that a
    /// form writes for each column, `None` where no form writes one, and a
    /// column past its end counts as `None`.
    ///
    /// Refuses a grid that marks a cell with `@` at a Position column, and
    /// one that marks none at an Offset column, the column after the grid's
    /// `before` values.
    pub(super) fn param_value(&mut self, rows: &[SExpr], columns: &[Option<TypeName>], record: &mut Record) -> R<ParamValue> {
        if let [row] = rows {
            if is_derivation(row) {
                return self.derivation(row, record);
            }
        }
        if rows.first().is_some_and(is_grid_row) {
            let mut grids = Vec::new();
            for row in rows {
                if !is_grid_row(row) {
                    return self.refuse("each row of a form whose first row is a grid is a grid", row.place());
                }
                grids.push(self.grid_rows(row, columns, record)?);
            }
            return Ok(ParamValue::Grids(grids.into()));
        }
        let mut values = Vec::new();
        for row in rows {
            values.push(self.row(row, record)?);
        }
        Ok(ParamValue::Rows(values.into()))
    }

    /// One row of values, `(3 1)`.
    fn row(&mut self, expr: &SExpr, record: &mut Record) -> R<Arc<[DataValue]>> {
        let list = self.list(expr, "a row")?;
        record.token(list.open);
        let mut values = Vec::new();
        for item in list.items {
            values.push(self.value(item, record)?);
        }
        record.token(list.close);
        Ok(values.into())
    }

    fn value(&mut self, expr: &SExpr, record: &mut Record) -> R<DataValue> {
        match expr {
            SExpr::Symbol { text, place } => {
                let value = self.symbol_value(text, *place)?;
                record.token(*place);
                Ok(value)
            }
            SExpr::List { .. } => Ok(DataValue::List(self.row(expr, record)?)),
            SExpr::String { place, .. } => self.refuse("a value is a number, a constant's name or a list", *place),
        }
    }

    fn symbol_value(&mut self, text: &str, place: SourcePlace) -> R<DataValue> {
        if let Ok(number) = text.parse::<i32>() {
            if number.to_string() == text {
                return Ok(DataValue::Integer(number));
            }
        }
        if is_constant_name(text) {
            return Ok(DataValue::Orientation(text.into()));
        }
        self.refuse(format!("`{text}` is not a number or a constant's name"), place)
    }

    /// `(grid ...)`, or the values before a grid and the grid,
    /// `(1 (grid ...))`.
    fn grid_rows(&mut self, expr: &SExpr, columns: &[Option<TypeName>], record: &mut Record) -> R<GridRows> {
        if head_of(expr) == Some(sp::GRID) {
            let grid = self.typed_grid(expr, columns, 0, record)?;
            return Ok(GridRows { before: Arc::new([]), grid });
        }
        let list = self.list(expr, "a row")?;
        record.token(list.open);
        let (last, before_items) = list.items.split_last().expect("a grid row ends in a grid");
        let mut before = Vec::new();
        for item in before_items {
            before.push(self.value(item, record)?);
        }
        let grid = self.typed_grid(last, columns, before.len(), record)?;
        record.token(list.close);
        Ok(GridRows { before: before.into(), grid })
    }

    /// The grid of `expr`, whose position column is the one of `columns`
    /// after `before` values.
    fn typed_grid(&mut self, expr: &SExpr, columns: &[Option<TypeName>], before: usize, record: &mut Record) -> R<Grid> {
        let grid = self.grid(expr, record)?;
        match (columns.get(before).copied().flatten(), grid.anchor) {
            (Some(TypeName::Position), Some(_)) => self.refuse("a grid of a Position column marks no cell with `@`", expr.place()),
            (Some(TypeName::Offset), None) => self.refuse("a grid of an Offset column marks one cell with `@`", expr.place()),
            _ => Ok(grid),
        }
    }

    /// Refuses a grid whose rows differ in length, and one that marks two
    /// cells with `@`.
    fn grid(&mut self, expr: &SExpr, record: &mut Record) -> R<Grid> {
        let list = self.list(expr, "a grid")?;
        if head_of(expr) != Some(sp::GRID) {
            return self.refuse("a grid is a `grid` form", list.place);
        }
        record.token(list.open);
        record.token(list.items[0].place());
        let mut rows = Vec::new();
        let mut anchor = None;
        for (row_index, item) in list.items[1..].iter().enumerate() {
            let row = self.list(item, "a grid's row")?;
            record.token(row.open);
            let mut cells = Vec::new();
            for (column, cell) in row.items.iter().enumerate() {
                if let SExpr::List { .. } = cell {
                    cells.push(Some(self.value(cell, record)?));
                    continue;
                }
                let (text, place) = self.symbol(Some(cell), "a grid's cell", row.place)?;
                let unmarked = match text.strip_prefix(sp::ANCHOR_MARK) {
                    Some(rest) => {
                        if anchor.is_some() {
                            return self.refuse("a grid marks one cell with `@`", place);
                        }
                        anchor = Some(GridCell { row: row_index as u32, column: column as u32 });
                        rest
                    }
                    None => text,
                };
                cells.push(if unmarked == sp::EMPTY_CELL { None } else { Some(self.symbol_value(unmarked, place)?) });
                record.token(place);
            }
            record.token(row.close);
            if rows.first().is_some_and(|first: &Arc<[Option<DataValue>]>| first.len() != cells.len()) {
                return self.refuse("a grid's rows are of one length", list.place);
            }
            rows.push(cells.into());
        }
        record.token(list.close);
        Ok(Grid { rows: rows.into(), anchor })
    }

    /// `(Frame ((:A AXIS_V) (:N 6)) ...)`: the derivation's name, then one
    /// list of fields per row.
    fn derivation(&mut self, expr: &SExpr, record: &mut Record) -> R<ParamValue> {
        let list = self.list(expr, "a derivation")?;
        record.token(list.open);
        let (name, place) = self.symbol(list.items.first(), "the derivation's name", list.place)?;
        record.token(place);
        let mut rows = Vec::new();
        for item in &list.items[1..] {
            let row = self.list(item, "a derivation's row")?;
            record.token(row.open);
            let mut fields = Vec::new();
            for field in row.items {
                let field_list = self.list(field, "a field")?;
                record.token(field_list.open);
                let (column, place) = self.symbol(field_list.items.first(), "a field's column", field_list.place)?;
                let Some(column) = column.strip_prefix(sp::COLUMN_MARK) else {
                    return self.refuse("a field's column is `:` and a name", place);
                };
                record.token(place);
                let Some(value) = field_list.items.get(1) else {
                    return self.refuse("the list lacks the field's value", field_list.place);
                };
                let value = self.value(value, record)?;
                self.no_more(field_list.items, 2)?;
                record.token(field_list.close);
                fields.push(DataField { column: ColumnName::Written(column.into()), value });
            }
            record.token(row.close);
            rows.push(fields.into());
        }
        record.token(list.close);
        Ok(ParamValue::Derivation { derivation: LibName(name.into()), rows: rows.into() })
    }

    fn exclude(&mut self, items: &[SExpr], at: SourcePlace, record: &mut Record) -> R<Exclude> {
        let Some(expr) = items.get(1) else { return self.refuse("the list lacks the excluded combination", at) };
        let list = self.list(expr, "the excluded combination")?;
        record.token(list.open);
        let mut combination = Vec::new();
        for item in list.items {
            let (name, place) = self.symbol(Some(item), "an alt's name", list.place)?;
            record.token(place);
            combination.push(AltsName(name.into()));
        }
        record.token(list.close);
        let reason = match items.get(2) {
            Some(expr) => {
                let (text, place) = self.string(Some(expr), "the reason", at)?;
                record.token(place);
                Some(Text(text.into()))
            }
            None => None,
        };
        self.no_more(items, 3)?;
        Ok(Exclude { combination: combination.into(), reason })
    }

    fn witness_record(&mut self, items: &[SExpr], at: SourcePlace, path: &NodePath, params: &[Node<Param>], record: &mut Record) -> R<WitnessRecord> {
        let (head, _) = self.symbol(items.first(), "a form's keyword", at)?;
        let (name, place) = self.symbol(items.get(1), "the form's name", at)?;
        record.token(place);
        if head == sp::ALTS_RECORD {
            let mut alts = Vec::new();
            for expr in &items[2..] {
                if head_of(expr) != Some(sp::ALT_RECORD) {
                    return self.refuse("an `alts` form holds `alt` forms after its name", expr.place());
                }
                let child = path.child(alts.len() as u32);
                alts.push(self.alt_record(expr, &child, params)?);
            }
            Ok(WitnessRecord::Alts { name: AltsName(name.into()), alts: alts.into() })
        } else {
            let witnesses = self.witnesses(&items[2..], path, params)?;
            Ok(WitnessRecord::Approximated { claim: Slug(name.into()), witnesses: witnesses.into() })
        }
    }

    fn witnesses(&mut self, exprs: &[SExpr], path: &NodePath, params: &[Node<Param>]) -> R<Vec<Witness>> {
        let mut witnesses = Vec::new();
        for expr in exprs {
            if head_of(expr) != Some(sp::WITNESS) {
                return self.refuse("the form holds `witness` forms here", expr.place());
            }
            let child = path.child(witnesses.len() as u32);
            witnesses.push(self.witness(expr, &child, params)?);
        }
        Ok(witnesses)
    }

    fn alt_record(&mut self, expr: &SExpr, path: &NodePath, params: &[Node<Param>]) -> R<AltRecord> {
        let list = self.list(expr, "an `alt` form")?;
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        record.token(list.items[0].place());
        let (name, place) = self.symbol(list.items.get(1), "the alt's name", list.place)?;
        record.token(place);
        let rest = &list.items[2..];
        let split = rest.iter().position(|e| head_of(e) == Some(sp::ALT_RECORD)).unwrap_or(rest.len());
        let witnesses = self.witnesses(&rest[..split], path, params)?;
        let mut nested = Vec::new();
        for expr in &rest[split..] {
            if head_of(expr) != Some(sp::ALT_RECORD) {
                return self.refuse("an `alt` form holds its witnesses before its nested `alt` forms", expr.place());
            }
            let child = path.child((witnesses.len() + nested.len()) as u32);
            nested.push(self.alt_record(expr, &child, params)?);
        }
        record.token(list.close);
        self.save(path, record);
        Ok(AltRecord { name: AltsName(name.into()), witnesses: witnesses.into(), nested: nested.into() })
    }

    fn witness(&mut self, expr: &SExpr, path: &NodePath, params: &[Node<Param>]) -> R<Witness> {
        let list = self.list(expr, "a `witness` form")?;
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        record.token(list.items[0].place());
        let (id, place) = self.symbol(list.items.get(1), "the witness's id", list.place)?;
        record.token(place);
        let (text, place) = self.symbol(list.items.get(2), "the witness's plausibility", list.place)?;
        let Some(plausibility) = parse(sp::PLAUSIBILITIES, text) else {
            return self.refuse(format!("`{text}` is not a plausibility"), place);
        };
        record.token(place);
        let (text, place) = self.symbol(list.items.get(3), "the witness's verdict", list.place)?;
        record.token(place);
        let verdict = match text {
            sp::CONCEPT => Verdict::Concept,
            sp::ANY => Verdict::Any,
            sp::OTHER => Verdict::Other,
            name => Verdict::Alt(AltsName(name.into())),
        };
        let body = if list.items.len() > 4 { Some(self.witness_body(&list.items[4..], list.place, path, params, &mut record)?) } else { None };
        record.token(list.close);
        self.save(path, record);
        Ok(Witness { id: id.into(), plausibility, verdict, body })
    }

    /// The body of a witness given in full: its `relaxed` forms, its
    /// `separates` form, whose tokens are the witness's own, its `assign`
    /// forms, its `input` form and its `output` forms. An `assign` form's
    /// columns take the types that the `param` form of its relation among
    /// `params` writes, and none where `params` holds none.
    fn witness_body(&mut self, items: &[SExpr], at: SourcePlace, path: &NodePath, params: &[Node<Param>], record: &mut Record) -> R<WitnessBody> {
        let mut rest = items;
        let mut child = 0u32;
        let mut relaxed = Vec::new();
        while let Some(expr) = rest.first().filter(|e| head_of(e) == Some(sp::RELAXED)) {
            let (list, mut own) = self.child_list(expr)?;
            let (slug, place) = self.symbol(list.items.get(1), "the relaxed claim's slug", list.place)?;
            own.token(place);
            self.no_more(list.items, 2)?;
            own.token(list.close);
            self.save(&path.child(child), own);
            child += 1;
            relaxed.push(Slug(slug.into()));
            rest = &rest[1..];
        }
        let Some(expr) = rest.first().filter(|e| head_of(e) == Some(sp::SEPARATES)) else {
            return self.refuse("a witness with a body holds a `separates` form after its `relaxed` forms", rest.first().map_or(at, SExpr::place));
        };
        let list = self.list(expr, "a `separates` form")?;
        record.token(list.open);
        record.token(list.items[0].place());
        let (separates, place) = self.string(list.items.get(1), "the feature the witness separates on", list.place)?;
        record.token(place);
        self.no_more(list.items, 2)?;
        record.token(list.close);
        rest = &rest[1..];
        let mut assigns = Vec::new();
        while let Some(expr) = rest.first().filter(|e| head_of(e) == Some(sp::ASSIGN)) {
            let (list, mut own) = self.child_list(expr)?;
            let (name, place) = self.symbol(list.items.get(1), "the assigned relation", list.place)?;
            let relation = self.program_relation(name, place)?;
            own.token(place);
            let written = match params.iter().find(|param| param.value().name == relation) {
                Some(param) => written_types(&param.value().columns),
                None => Vec::new(),
            };
            let value = self.param_value(&list.items[2..], &written, &mut own)?;
            own.token(list.close);
            self.save(&path.child(child), own);
            child += 1;
            assigns.push((relation, value));
            rest = &rest[1..];
        }
        let Some(expr) = rest.first().filter(|e| head_of(e) == Some(sp::INPUT)) else {
            return self.refuse("a witness with a body holds an `input` form after its `assign` forms", rest.first().map_or(at, SExpr::place));
        };
        let (list, mut own) = self.child_list(expr)?;
        let Some(grid) = list.items.get(1) else { return self.refuse("the list lacks the input grid", list.place) };
        let input = self.grid(grid, &mut own)?;
        self.no_more(list.items, 2)?;
        own.token(list.close);
        self.save(&path.child(child), own);
        child += 1;
        let mut outputs = Vec::new();
        for expr in &rest[1..] {
            if head_of(expr) != Some(sp::OUTPUT) {
                return self.refuse("a witness holds `output` forms after its `input` form", expr.place());
            }
            let (list, mut own) = self.child_list(expr)?;
            outputs.push(self.witness_output(&list.items[1..], list.place, &mut own)?);
            own.token(list.close);
            self.save(&path.child(child), own);
            child += 1;
        }
        Ok(WitnessBody {
            relaxed: relaxed.into(),
            separates: Text(separates.into()),
            assigns: assigns.into(),
            input,
            outputs: outputs.into(),
        })
    }

    /// The list of a child form with no children of its own, and its record
    /// with its `(` and its keyword.
    fn child_list<'e>(&mut self, expr: &'e SExpr) -> R<(List<'e>, Record)> {
        let list = self.list(expr, "a form")?;
        let mut own = Record::new(Some(list.place));
        own.token(list.open);
        own.token(list.items[0].place());
        Ok((list, own))
    }

    fn witness_output(&mut self, items: &[SExpr], at: SourcePlace, record: &mut Record) -> R<WitnessOutput> {
        let mut names = Vec::new();
        let mut rest = items;
        while let Some(expr) = rest.first().filter(|e| !is_output_value(e)) {
            let group = self.name_group(expr, record)?;
            names.push(group.into_iter().map(|(text, _)| case_ref(text)).collect());
            rest = &rest[1..];
        }
        let value = match rest {
            [] => return self.refuse("the list lacks the output", at),
            [SExpr::Symbol { text, place }] if &**text == sp::UNDEFINED => {
                record.token(*place);
                OutputValue::Undefined
            }
            grids => {
                let mut read = Vec::new();
                for grid in grids {
                    read.push(self.grid(grid, record)?);
                }
                OutputValue::Grids(read.into())
            }
        };
        Ok(WitnessOutput { names: names.into(), value })
    }
}

/// A top-level form of an arcdata file.
enum Top {
    Representative(Representative),
    Param(Node<Param>),
    Exclude(Exclude),
    Record(WitnessRecord),
}

impl Top {
    /// The form's place in the order of the file's forms.
    fn rank(&self) -> u8 {
        match self {
            Top::Representative(_) => 0,
            Top::Param(_) => 1,
            Top::Exclude(_) => 2,
            Top::Record(_) => 3,
        }
    }
}

/// The column types of a `param` form, each as a type a form writes.
fn written_types(columns: &[TypeName]) -> Vec<Option<TypeName>> {
    columns.iter().copied().map(Some).collect()
}

fn case_ref(text: &str) -> CaseRef {
    if text == sp::CONCEPT { CaseRef::Concept } else { CaseRef::Alt(AltsName(text.into())) }
}

/// Whether `expr` is the output of an `output` form: `undefined` or a grid.
fn is_output_value(expr: &SExpr) -> bool {
    matches!(expr, SExpr::Symbol { text, .. } if &**text == sp::UNDEFINED) || head_of(expr) == Some(sp::GRID)
}

/// Whether `text` is an orientation constant's name, such as `DIR_T` or
/// `D4_CC`: capitals, digits and `_`, from a capital.
fn is_constant_name(text: &str) -> bool {
    let mut chars = text.chars();
    chars.next().is_some_and(|c| c.is_ascii_uppercase())
        && chars.all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || c == '_')
}

/// Whether `expr` is a grid row: `(grid ...)`, or a list whose last item is
/// one.
fn is_grid_row(expr: &SExpr) -> bool {
    head_of(expr) == Some(sp::GRID)
        || matches!(expr, SExpr::List { items, .. } if items.last().is_some_and(|last| head_of(last) == Some(sp::GRID)))
}

/// Whether `expr` is a derivation: a name, then lists of fields, each field
/// a list headed by a `:` column.
fn is_derivation(expr: &SExpr) -> bool {
    let SExpr::List { items, .. } = expr else { return false };
    let [SExpr::Symbol { .. }, rows @ ..] = &items[..] else { return false };
    !rows.is_empty()
        && rows.iter().all(|row| match row {
            SExpr::List { items: fields, .. } => fields.iter().all(|field| {
                matches!(head_of(field), Some(column) if column.starts_with(sp::COLUMN_MARK))
            }),
            _ => false,
        })
}
