//! The writer of an arcdata file from its nodes and its layout. It walks
//! the nodes in the order the reader of `engine/arclog/src/read/arcdata.rs`
//! reads them, and writes each token through [`super::arclog::Out`], at the
//! place its node's layout gives.

use crate::layout::{Layout, SourceFile};
use crate::program::path::NodePath;
use crate::program::*;
use crate::read::spelling::{self as sp, spelling};

use super::arclog::{program_relation, quoted, Out, Tokens};

const FILE: SourceFile = SourceFile::Arcdata;

struct Writer<'l> {
    layout: &'l Layout,
    out: Out<'l>,
}

/// The text of `value`, as the file writes it.
fn value_text(value: &DataValue) -> Option<String> {
    match value {
        DataValue::Integer(number) => Some(number.to_string()),
        DataValue::Orientation(name) => Some(name.to_string()),
        DataValue::List(_) => None,
    }
}

impl<'l> Writer<'l> {
    fn tokens(&self, path: &NodePath) -> Tokens<'l> {
        Tokens::of(self.layout, FILE, path)
    }

    fn put(&mut self, t: &mut Tokens, text: &str) {
        self.out.next_token(t, text);
    }

    fn arcdata(&mut self, arcdata: &Arcdata) {
        let root = NodePath::default();
        let mut next = 0u32;
        if let Some(representative) = &arcdata.representative {
            self.form(&root.child(next), sp::REPRESENTATIVE, |w, t| {
                w.put(t, &representative.task_id);
                if let Some(case) = &representative.case {
                    w.names(t, case.iter().map(|name| &*name.0));
                }
            });
            next += 1;
        }
        for param in arcdata.params.iter() {
            let param = param.value();
            self.form(&root.child(next), sp::PARAM, |w, t| {
                w.put(t, &program_relation(&param.name));
                w.names(t, param.columns.iter().map(|ty| spelling(sp::TYPE_NAMES, ty)));
                w.param_value(t, &param.value);
            });
            next += 1;
        }
        for exclude in arcdata.excludes.iter() {
            self.form(&root.child(next), sp::EXCLUDE, |w, t| {
                w.put(t, "(");
                for name in exclude.combination.iter() {
                    w.put(t, &name.0);
                }
                w.put(t, ")");
                if let Some(reason) = &exclude.reason {
                    w.put(t, &quoted(&reason.0));
                }
            });
            next += 1;
        }
        for record in arcdata.witness_records.iter() {
            let path = root.child(next);
            match record {
                WitnessRecord::Alts { name, alts } => self.form(&path, sp::ALTS_RECORD, |w, t| {
                    w.put(t, &name.0);
                    for (index, alt) in alts.iter().enumerate() {
                        w.alt_record(alt, &path.child(index as u32));
                    }
                }),
                WitnessRecord::Approximated { claim, witnesses } => self.form(&path, sp::APPROXIMATED_RECORD, |w, t| {
                    w.put(t, &claim.0);
                    w.witnesses(witnesses, &path, 0);
                }),
            }
            next += 1;
        }
    }

    /// The form at `path`: its `(`, its keyword, what `body` writes, and its
    /// `)`.
    fn form(&mut self, path: &NodePath, keyword: &str, body: impl FnOnce(&mut Self, &mut Tokens<'l>)) {
        let mut t = self.tokens(path);
        self.put(&mut t, "(");
        self.put(&mut t, keyword);
        body(self, &mut t);
        self.put(&mut t, ")");
    }

    /// One name bare, or several as a list.
    fn names<'n>(&mut self, t: &mut Tokens, names: impl ExactSizeIterator<Item = &'n str>) {
        let list = names.len() != 1;
        if list {
            self.put(t, "(");
        }
        for name in names {
            self.put(t, name);
        }
        if list {
            self.put(t, ")");
        }
    }

    fn param_value(&mut self, t: &mut Tokens, value: &ParamValue) {
        match value {
            ParamValue::Rows(rows) => {
                for row in rows.iter() {
                    self.row(t, row);
                }
            }
            ParamValue::Grids(grids) => {
                for grid_rows in grids.iter() {
                    if grid_rows.before.is_empty() {
                        self.grid(t, &grid_rows.grid);
                    } else {
                        self.put(t, "(");
                        for value in grid_rows.before.iter() {
                            self.value(t, value);
                        }
                        self.grid(t, &grid_rows.grid);
                        self.put(t, ")");
                    }
                }
            }
            ParamValue::Derivation { derivation, rows } => {
                self.put(t, "(");
                self.put(t, &derivation.0);
                for row in rows.iter() {
                    self.put(t, "(");
                    for field in row.iter() {
                        self.put(t, "(");
                        let ColumnName::Written(column) = &field.column else {
                            panic!("a derivation's field is read from a file, which writes its column")
                        };
                        self.put(t, &format!("{}{column}", sp::COLUMN_MARK));
                        self.value(t, &field.value);
                        self.put(t, ")");
                    }
                    self.put(t, ")");
                }
                self.put(t, ")");
            }
        }
    }

    fn row(&mut self, t: &mut Tokens, row: &[DataValue]) {
        self.put(t, "(");
        for value in row {
            self.value(t, value);
        }
        self.put(t, ")");
    }

    fn value(&mut self, t: &mut Tokens, value: &DataValue) {
        match value {
            DataValue::List(values) => self.row(t, values),
            atom => self.put(t, &value_text(atom).expect("a value that is no list has a text")),
        }
    }

    fn grid(&mut self, t: &mut Tokens, grid: &Grid) {
        self.put(t, "(");
        self.put(t, sp::GRID);
        for (row_index, row) in grid.rows.iter().enumerate() {
            self.put(t, "(");
            for (column, cell) in row.iter().enumerate() {
                let text = match cell {
                    Some(DataValue::List(values)) => {
                        self.row(t, values);
                        continue;
                    }
                    Some(value) => value_text(value).expect("a value that is no list has a text"),
                    None => sp::EMPTY_CELL.to_owned(),
                };
                let anchored = grid.anchor == Some(GridCell { row: row_index as u32, column: column as u32 });
                if anchored {
                    self.put(t, &format!("{}{text}", sp::ANCHOR_MARK));
                } else {
                    self.put(t, &text);
                }
            }
            self.put(t, ")");
        }
        self.put(t, ")");
    }

    fn alt_record(&mut self, alt: &AltRecord, path: &NodePath) {
        self.form(path, sp::ALT_RECORD, |w, t| {
            w.put(t, &alt.name.0);
            w.witnesses(&alt.witnesses, path, 0);
            for (index, nested) in alt.nested.iter().enumerate() {
                w.alt_record(nested, &path.child((alt.witnesses.len() + index) as u32));
            }
        });
    }

    fn witnesses(&mut self, witnesses: &[Witness], parent: &NodePath, first: u32) {
        for (index, witness) in witnesses.iter().enumerate() {
            self.witness(witness, &parent.child(first + index as u32));
        }
    }

    fn witness(&mut self, witness: &Witness, path: &NodePath) {
        self.form(path, sp::WITNESS, |w, t| {
            w.put(t, &witness.id);
            w.put(t, spelling(sp::PLAUSIBILITIES, &witness.plausibility));
            let verdict = match &witness.verdict {
                Verdict::Concept => sp::CONCEPT,
                Verdict::Any => sp::ANY,
                Verdict::Other => sp::OTHER,
                Verdict::Alt(name) => &name.0,
            };
            w.put(t, verdict);
            if let Some(body) = &witness.body {
                w.witness_body(t, body, path);
            }
        });
    }

    fn witness_body(&mut self, t: &mut Tokens, body: &WitnessBody, path: &NodePath) {
        let mut child = 0u32;
        let mut next = || {
            child += 1;
            path.child(child - 1)
        };
        for slug in body.relaxed.iter() {
            self.form(&next(), sp::RELAXED, |w, own| w.put(own, &slug.0));
        }
        self.put(t, "(");
        self.put(t, sp::SEPARATES);
        self.put(t, &quoted(&body.separates.0));
        self.put(t, ")");
        for (relation, value) in body.assigns.iter() {
            self.form(&next(), sp::ASSIGN, |w, own| {
                w.put(own, &program_relation(relation));
                w.param_value(own, value);
            });
        }
        self.form(&next(), sp::INPUT, |w, own| w.grid(own, &body.input));
        for output in body.outputs.iter() {
            self.form(&next(), sp::OUTPUT, |w, own| {
                for names in output.names.iter() {
                    w.names(
                        own,
                        names.iter().map(|name| match name {
                            CaseRef::Concept => sp::CONCEPT,
                            CaseRef::Alt(name) => &*name.0,
                        }),
                    );
                }
                match &output.value {
                    OutputValue::Undefined => w.put(own, sp::UNDEFINED),
                    OutputValue::Grids(grids) => {
                        for grid in grids.iter() {
                            w.grid(own, grid);
                        }
                    }
                }
            });
        }
    }
}

pub(super) fn write(arcdata: &Arcdata, layout: &Layout) -> String {
    let mut writer = Writer { layout, out: Out::new(layout, FILE) };
    writer.arcdata(arcdata);
    let end = writer.tokens(&NodePath::default()).first();
    writer.out.finish(end, FILE)
}
