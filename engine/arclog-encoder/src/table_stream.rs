//! A task's tables as a tables command gives them, from a framed binary stream of typed column arrays
//! or from the JSON text of a tables file. A table's rows are read into column arrays in the cell
//! encoding as their frame arrives, and `TableIn::stored` makes the `Stored` table from them.
//!
//! The stream starts with [`MAGIC`] and holds frames. A frame is a tag byte, a header's length as
//! 4 bytes, the header as JSON, a body's length as 8 bytes, and the body. All numbers are little-endian.
//!
//! - `H`: the task's head, with every field of a tables file but `items` and `prefix`. It comes first.
//! - `P`: a table of the state, whose header's `name` names it, read with all its rows.
//! - `I`: an item. Its header holds the item's fields, and `mutants`, a list of the fields of each of its
//!   mutants. It is followed by one `T` frame for its gold table and one for each mutant's table, in order.
//! - `T`: a candidate's table, read with all its rows.
//! - `E`: the end of the stream.
//!
//! A table's header holds its fields as a tables file writes them, but for `rows` and `models`, and
//! also `widths`, `layout` and `orient`. `widths` is how many 4-byte numbers each column takes at a row:
//! 4 for a column of boxes, a margin each, and 1 for any other. `layout` lists, for each example key
//! (`train/0`, `test/0` or `task`), the row count of each of its TableRows. `orient` names the orientation
//! constant of each number that an orientation column holds. The body holds, for each key of `layout`,
//! each TableRows, and each column of it, that column's numbers as 4-byte integers, one cell after another.

use std::collections::BTreeMap;
use std::io::Read;

use arclog::registry::Registry;
use arclog::terms::{Color, Constant, Margins, Term, TermId};
use arclog::types::ValueType;
use serde_json::Value;

use crate::lookup::LookupMap;
use crate::stored::{Model, Stored};

pub const MAGIC: &[u8; 8] = b"ARCTBL1\n";

/// The rows of a table as they were read, before the tables of `Stored` are made from them.
pub enum Rows {
    /// Column arrays in the cell encoding, one list of TableRows per example, or where `repeat` holds a count,
    /// the one list that stands at each of that many examples.
    Models { types: Vec<ValueType>, columns: Value, examples: Vec<Vec<Model>>, repeat: Option<usize> },
    /// A tables file's `types`, `columns`, `rows` and `models`, which `Stored::of_json` reads.
    Json { value: Value, train: usize, test: usize },
}

impl Rows {
    /// The table, made anew at each call. It is none where a cell does not read.
    pub fn build(&self) -> Option<Stored> {
        match self {
            Rows::Models { types, columns, examples, repeat } => {
                let mut stored = match repeat {
                    Some(count) => Stored::of_models(types, std::iter::repeat(&examples[0]).take(*count)),
                    None => Stored::of_models(types, examples.iter()),
                };
                stored.set_keys(types, columns);
                Some(stored)
            }
            Rows::Json { value, train, test } => Stored::of_json(value, *train, *test),
        }
    }
}

/// A table of a task: its fields as a tables file writes them, but for its rows, and its rows
/// where they can be read.
pub struct TableIn {
    pub meta: Value,
    pub rows: Option<Rows>,
}

impl TableIn {
    /// The table made from the rows, or none where they can't be stored. A caller makes it where
    /// it uses it, so that the tables of a run are made in the order that it uses them.
    pub fn stored(&self) -> Option<Stored> {
        self.rows.as_ref()?.build()
    }
}

pub struct MutantIn {
    pub meta: Value,
    pub table: TableIn,
}

pub struct ItemIn {
    pub meta: Value,
    pub gold: TableIn,
    pub mutants: Vec<MutantIn>,
}

/// A tables file's content: `head` holds every field but the items and the tables of the state.
pub struct TablesIn {
    pub head: Value,
    pub prefix: BTreeMap<String, TableIn>,
    pub items: Vec<ItemIn>,
}

/// The field `key` of a value, which the value gives up, or null where it has none.
fn take(value: &mut Value, key: &str) -> Value {
    value.get_mut(key).map(Value::take).unwrap_or(Value::Null)
}

fn counts_of(head: &Value) -> Result<(usize, usize), String> {
    head["task"].as_str().ok_or("a file's task")?;
    let train = head["train"].as_u64().ok_or("a file's train")? as usize;
    let test = head["test"].as_u64().unwrap_or(0) as usize;
    Ok((train, test))
}

impl TablesIn {
    /// The tables of a tables file's text.
    pub fn from_json(text: &str) -> Result<TablesIn, String> {
        let mut data: Value = serde_json::from_str(text).map_err(|error| error.to_string())?;
        let (train, test) = counts_of(&data)?;
        let table_of = |mut value: Value| -> TableIn {
            let mut held = serde_json::Map::new();
            held.insert("types".to_string(), value["types"].clone());
            held.insert("columns".to_string(), value["columns"].clone());
            if let Some(fields) = value.as_object_mut() {
                for key in ["rows", "models"] {
                    if let Some(rows) = fields.remove(key) {
                        held.insert(key.to_string(), rows);
                    }
                }
            }
            TableIn { meta: value, rows: Some(Rows::Json { value: Value::Object(held), train, test }) }
        };
        let mut prefix = BTreeMap::new();
        if let Some(tables) = data.get_mut("prefix").and_then(Value::as_object_mut) {
            for (name, value) in std::mem::take(tables) {
                prefix.insert(name, table_of(value));
            }
        }
        let mut items = Vec::new();
        let listed = match take(&mut data, "items") {
            Value::Array(listed) => listed,
            _ => return Err("a file's items".to_string()),
        };
        for mut item in listed {
            let gold = table_of(take(&mut item, "gold"));
            let mutants = match take(&mut item, "mutants") {
                Value::Array(mutants) => mutants,
                _ => return Err("an item's mutants".to_string()),
            };
            let mutants = mutants.into_iter().map(|mut mutant| {
                let table = table_of(take(&mut mutant, "table"));
                MutantIn { meta: mutant, table }
            }).collect();
            items.push(ItemIn { meta: item, gold, mutants });
        }
        if let Some(fields) = data.as_object_mut() {
            fields.remove("prefix");
            fields.remove("items");
        }
        Ok(TablesIn { head: data, prefix, items })
    }

    /// The tables that a reader gives: a stream of frames where it starts with [`MAGIC`], and a
    /// tables file's text otherwise.
    pub fn from_reader<R: Read>(mut reader: R) -> Result<TablesIn, String> {
        let mut first = [0u8; 8];
        let mut got = 0;
        while got < first.len() {
            match reader.read(&mut first[got..]) {
                Ok(0) => break,
                Ok(count) => got += count,
                Err(error) => return Err(error.to_string()),
            }
        }
        if got == first.len() && first == *MAGIC {
            return read_frames(&mut reader);
        }
        let mut bytes = first[..got].to_vec();
        reader.read_to_end(&mut bytes).map_err(|error| error.to_string())?;
        let text = String::from_utf8(bytes).map_err(|error| error.to_string())?;
        TablesIn::from_json(&text)
    }
}

struct Frame {
    tag: u8,
    header: Value,
    body: Vec<u8>,
}

fn read_frame<R: Read>(reader: &mut R) -> Result<Frame, String> {
    let short = |error: std::io::Error| format!("the stream ends inside a frame: {error}");
    let mut tag = [0u8; 1];
    reader.read_exact(&mut tag).map_err(short)?;
    let mut length = [0u8; 4];
    reader.read_exact(&mut length).map_err(short)?;
    let mut header = vec![0u8; u32::from_le_bytes(length) as usize];
    reader.read_exact(&mut header).map_err(short)?;
    let header: Value = serde_json::from_slice(&header).map_err(|error| error.to_string())?;
    let mut length = [0u8; 8];
    reader.read_exact(&mut length).map_err(short)?;
    let length = u64::from_le_bytes(length);
    if length > 1 << 36 {
        return Err("a frame's body is too long".to_string());
    }
    let mut body = vec![0u8; length as usize];
    reader.read_exact(&mut body).map_err(short)?;
    Ok(Frame { tag: tag[0], header, body })
}

fn read_frames<R: Read>(reader: &mut R) -> Result<TablesIn, String> {
    let mut reader = std::io::BufReader::with_capacity(1 << 20, reader);
    let head = read_frame(&mut reader)?;
    if head.tag != b'H' {
        return Err("the stream does not start with a head".to_string());
    }
    let (train, test) = counts_of(&head.header)?;
    let mut prefix = BTreeMap::new();
    let mut items = Vec::new();
    let table_of = |frame: Frame| -> TableIn {
        let rows = decode_table(&frame.header, &frame.body, train, test);
        TableIn { meta: frame.header, rows }
    };
    loop {
        let frame = read_frame(&mut reader)?;
        match frame.tag {
            b'P' => {
                let name = frame.header["name"].as_str().ok_or("a prefix table's name")?.to_string();
                prefix.insert(name, table_of(frame));
            }
            b'I' => {
                let mut meta = frame.header;
                let mutants = match take(&mut meta, "mutants") {
                    Value::Array(mutants) => mutants,
                    _ => return Err("an item's mutants".to_string()),
                };
                let next = |reader: &mut std::io::BufReader<&mut R>| -> Result<TableIn, String> {
                    let frame = read_frame(reader)?;
                    if frame.tag != b'T' {
                        return Err("an item's table is missing".to_string());
                    }
                    Ok(table_of(frame))
                };
                let gold = next(&mut reader)?;
                let mut held = Vec::with_capacity(mutants.len());
                for mutant in mutants {
                    held.push(MutantIn { meta: mutant, table: next(&mut reader)? });
                }
                items.push(ItemIn { meta, gold, mutants: held });
            }
            b'E' => return Ok(TablesIn { head: head.header, prefix, items }),
            _ => return Err("a frame has an unknown tag".to_string()),
        }
    }
}

/// How a column's numbers become cells.
#[derive(Clone, Copy, PartialEq)]
enum Kind {
    Box,
    Color,
    Example,
    Number,
    Ident,
    Orientation,
}

fn kind_of(ty: &ValueType) -> Kind {
    match ty {
        ty if ty.is_box() => Kind::Box,
        ValueType::Color => Kind::Color,
        ValueType::Example => Kind::Example,
        ValueType::Int | ValueType::Nat => Kind::Number,
        ValueType::Ident(_) => Kind::Ident,
        _ => Kind::Orientation,
    }
}

fn number_at(bytes: &[u8], at: usize) -> i32 {
    i32::from_le_bytes([bytes[at * 4], bytes[at * 4 + 1], bytes[at * 4 + 2], bytes[at * 4 + 3]])
}

/// The cells of one column of `rows` rows: `bytes` holds its numbers, and `names` the encoding of each
/// number that an orientation constant stands for.
fn column_of(kind: Kind, bytes: &[u8], rows: usize, names: &mut Orientations) -> Option<Vec<u32>> {
    let mut cells = Vec::with_capacity(rows);
    match kind {
        Kind::Box => {
            for row in 0..rows {
                let margins = Margins { top: number_at(bytes, row * 4), bottom: number_at(bytes, row * 4 + 1), left: number_at(bytes, row * 4 + 2), right: number_at(bytes, row * 4 + 3) };
                cells.push(Term::Box(margins).encode().ok().map(TermId::encoding)?);
            }
        }
        Kind::Color => {
            for row in 0..rows {
                let digit = u64::try_from(number_at(bytes, row)).ok()? as u8;
                cells.push(Term::Constant(Constant::Color(Color::from_digit(digit)?)).encode().ok().map(TermId::encoding)?);
            }
        }
        Kind::Example => {
            for row in 0..rows {
                let at = u16::try_from(u64::try_from(number_at(bytes, row)).ok()?).ok()?;
                cells.push(Term::Constant(Constant::Example(arclog::terms::Example::at(at))).encode().ok().map(TermId::encoding)?);
            }
        }
        Kind::Number | Kind::Ident => {
            for row in 0..rows {
                cells.push(number_at(bytes, row) as u32);
            }
        }
        Kind::Orientation => {
            for row in 0..rows {
                cells.push(names.encoding(number_at(bytes, row))?);
            }
        }
    }
    Some(cells)
}

/// The orientation constants of a table's numbers, each looked up once.
struct Orientations {
    named: LookupMap<i32, String>,
    found: LookupMap<i32, Option<u32>>,
}

impl Orientations {
    fn encoding(&mut self, number: i32) -> Option<u32> {
        if let Some(found) = self.found.get(&number) {
            return *found;
        }
        let found = self.named.get(&number).and_then(|name| {
            let constant = Registry::get().orientation_constant(name)?;
            Term::Constant(Constant::Orientation(constant)).encode().ok().map(TermId::encoding)
        });
        self.found.insert(number, found);
        found
    }
}

/// The rows of a candidate's or a state's table frame, as `Stored::of_json` reads them:
/// a cell that does not read leaves no table.
fn decode_table(meta: &Value, body: &[u8], train: usize, test: usize) -> Option<Rows> {
    let names = meta["types"].as_array()?;
    let types: Vec<ValueType> = names.iter().map(|name| crate::schema::type_of_name(name.as_str()?)).collect::<Option<_>>()?;
    let kinds: Vec<Kind> = types.iter().map(kind_of).collect();
    let widths: Vec<usize> = meta["widths"].as_array()?.iter().map(|width| width.as_u64().map(|width| width as usize)).collect::<Option<_>>()?;
    if widths.len() != types.len() || widths.iter().zip(&kinds).any(|(width, kind)| *width != if *kind == Kind::Box { 4 } else { 1 }) {
        return None;
    }
    let mut orientations = Orientations { named: LookupMap::new(), found: LookupMap::new() };
    for (number, name) in meta["orient"].as_object()? {
        orientations.named.insert(number.parse().ok()?, name.as_str()?.to_string());
    }
    let per_row: usize = widths.iter().sum();
    // Where each key's TableRows stand in the body, and how many rows each has.
    let mut places: LookupMap<&str, (usize, Vec<usize>)> = LookupMap::new();
    let mut at = 0usize;
    for entry in meta["layout"].as_array()? {
        let key = entry.get(0)?.as_str()?;
        let counts: Vec<usize> = entry.get(1)?.as_array()?.iter().map(|count| count.as_u64().map(|count| count as usize)).collect::<Option<_>>()?;
        let size: usize = counts.iter().sum::<usize>() * per_row * 4;
        places.insert(key, (at, counts));
        at += size;
    }
    if at != body.len() {
        return None;
    }
    // The TableRows at a key, in order.
    let mut read_at = |key: &str| -> Option<Vec<Model>> {
        let Some((start, counts)) = places.get(key) else { return Some(Vec::new()) };
        let mut at = *start;
        let mut models = Vec::with_capacity(counts.len());
        for rows in counts {
            let mut columns = Vec::with_capacity(types.len());
            for (kind, width) in kinds.iter().zip(&widths) {
                let size = rows * width * 4;
                columns.push(column_of(*kind, &body[at..at + size], *rows, &mut orientations)?);
                at += size;
            }
            models.push(Model { rows: *rows, columns });
        }
        Some(models)
    };
    let mut examples = Vec::with_capacity(train + test);
    let mut repeat = None;
    if places.contains_key("task") {
        examples.push(read_at("task")?);
        repeat = Some(train + test);
    } else {
        for pair in 0..train {
            examples.push(read_at(&format!("train/{pair}"))?);
        }
        for pair in 0..test {
            examples.push(read_at(&format!("test/{pair}"))?);
        }
    }
    Some(Rows::Models { types, columns: meta["columns"].clone(), examples, repeat })
}
