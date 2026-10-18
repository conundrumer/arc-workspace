//! The writer of an arcdata file from its nodes and its layout. It walks
//! the nodes in the order the reader of `engine/arclog/src/read/arcdata.rs`
//! reads them, and writes each token through [`super::arclog::Out`], at the
//! place its node's layout gives.

use crate::layout::{Layout, SourceFile};
use crate::program::path::{DataNodeRef, NodePath};
use crate::program::*;
use crate::read::spelling::{self as sp, spelling};

use super::arclog::{address_of, child_path, program_relation, quoted, Out, PathNode, Tokens};

const FILE: SourceFile = SourceFile::Arcdata;

struct Writer<'l> {
    layout: &'l Layout,
    out: Out<'l>,
}

impl PathNode for DataNodeRef<'_> {
    fn children(self) -> Vec<Self> {
        DataNodeRef::children(self)
    }

    fn address(self) -> *const () {
        match self {
            DataNodeRef::Arcdata(node) => address_of(node),
            DataNodeRef::Representative(node) => address_of(node),
            DataNodeRef::Param(node) => address_of(node),
            DataNodeRef::Exclude(node) => address_of(node),
            DataNodeRef::WitnessRecord(node) => address_of(node),
            DataNodeRef::AltRecord(node) => address_of(node),
            DataNodeRef::Witness(node) => address_of(node),
            DataNodeRef::Relaxed(node) => address_of(node),
            DataNodeRef::Assign(node) => address_of(node),
            DataNodeRef::Grid(node) => address_of(node),
            DataNodeRef::WitnessOutput(node) => address_of(node),
        }
    }
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
        let at = |child: DataNodeRef| child_path(&root, DataNodeRef::Arcdata(arcdata), child);
        if let Some(representative) = &arcdata.representative {
            self.form(&at(DataNodeRef::Representative(representative)), sp::REPRESENTATIVE, |w, t| {
                w.put(t, &representative.task_id);
                if let Some(case) = &representative.case {
                    w.names(t, case.iter().map(|name| &*name.0));
                }
            });
        }
        for node in arcdata.params.iter() {
            let param = node.value();
            self.form(&at(DataNodeRef::Param(node)), sp::PARAM, |w, t| {
                w.put(t, &program_relation(&param.name));
                w.names(t, param.columns.iter().map(|ty| spelling(sp::TYPE_NAMES, ty)));
                w.param_value(t, &param.value);
            });
        }
        for exclude in arcdata.excludes.iter() {
            self.form(&at(DataNodeRef::Exclude(exclude)), sp::EXCLUDE, |w, t| {
                w.put(t, "(");
                for name in exclude.combination.iter() {
                    w.put(t, &name.0);
                }
                w.put(t, ")");
                if let Some(reason) = &exclude.reason {
                    w.put(t, &quoted(&reason.0));
                }
            });
        }
        for record in arcdata.witness_records.iter() {
            let own = DataNodeRef::WitnessRecord(record);
            let path = at(own);
            match record {
                WitnessRecord::Alts { name, alts } => self.form(&path, sp::ALTS_RECORD, |w, t| {
                    w.put(t, &name.0);
                    for alt in alts.iter() {
                        w.alt_record(alt, &child_path(&path, own, DataNodeRef::AltRecord(alt)));
                    }
                }),
                WitnessRecord::Approximated { claim, witnesses } => self.form(&path, sp::APPROXIMATED_RECORD, |w, t| {
                    w.put(t, &claim.0);
                    w.witnesses(witnesses, own, &path);
                }),
            }
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
            let own = DataNodeRef::AltRecord(alt);
            w.witnesses(&alt.witnesses, own, path);
            for nested in alt.nested.iter() {
                w.alt_record(nested, &child_path(path, own, DataNodeRef::AltRecord(nested)));
            }
        });
    }

    /// The witnesses of `parent`, the node at `path`.
    fn witnesses(&mut self, witnesses: &[Witness], parent: DataNodeRef, path: &NodePath) {
        for witness in witnesses.iter() {
            self.witness(witness, &child_path(path, parent, DataNodeRef::Witness(witness)));
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
                w.witness_body(t, witness, body, path);
            }
        });
    }

    /// The body of `witness`, the node at `path`.
    fn witness_body(&mut self, t: &mut Tokens, witness: &Witness, body: &WitnessBody, path: &NodePath) {
        let at = |child: DataNodeRef| child_path(path, DataNodeRef::Witness(witness), child);
        for slug in body.relaxed.iter() {
            self.form(&at(DataNodeRef::Relaxed(slug)), sp::RELAXED, |w, own| w.put(own, &slug.0));
        }
        self.put(t, "(");
        self.put(t, sp::SEPARATES);
        self.put(t, &quoted(&body.separates.0));
        self.put(t, ")");
        for assign in body.assigns.iter() {
            let (relation, value) = assign;
            self.form(&at(DataNodeRef::Assign(assign)), sp::ASSIGN, |w, own| {
                w.put(own, &program_relation(relation));
                w.param_value(own, value);
            });
        }
        self.form(&at(DataNodeRef::Grid(&body.input)), sp::INPUT, |w, own| w.grid(own, &body.input));
        for output in body.outputs.iter() {
            self.form(&at(DataNodeRef::WitnessOutput(output)), sp::OUTPUT, |w, own| {
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
