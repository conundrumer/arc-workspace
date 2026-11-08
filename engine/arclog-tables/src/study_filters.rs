//! Study filters on complete table values. No tokens, repaired identities,
//! Python normalizer, or filesystem access participates in these operations.
pub mod equality;
pub mod normal;
pub mod recovery;
pub mod recovery_ext;

use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

pub type Cell = Vec<i32>;
pub type Row = Vec<Cell>;
pub type Rows = BTreeSet<Row>;
pub type Result<T> = std::result::Result<T, String>;

/// The work of one study filter, counted against `max_work`. A stop at the
/// cap depends on the filter's inputs alone, with no clock.
pub struct Work {
    left: u64,
    initial: u64,
}
impl Work {
    pub fn new(limit: u64) -> Self {
        Self { left: limit, initial: limit }
    }
    pub fn charge(&mut self, n: usize) -> Result<()> {
        if n as u64 > self.left {
            return Err("stopped:Work".into());
        }
        self.left -= n as u64;
        Ok(())
    }
    pub fn used(&self) -> u64 {
        self.initial - self.left
    }
    /// The cap, `max_work`.
    pub fn cap(&self) -> u64 {
        self.initial
    }
}

/// One table, at one specified DET assignment. Rows are sets, separately
/// at every input. A scalar is one i32 and a Box/Offset four margins.
#[derive(Clone, Debug)]
pub struct Table {
    pub types: Vec<String>,
    pub names: Vec<String>,
    pub rows: Vec<Rows>,
    pub flows: Vec<Vec<(u8, i64)>>,
    pub meta: Value,
}
pub fn width(ty: &str) -> usize {
    if matches!(ty, "Box" | "Position" | "Offset") {
        4
    } else {
        1
    }
}
pub fn recovery_type(ty: &str) -> &str {
    match ty {
        "Position" => "Box",
        "number" | "Int" | "Nat" => "Number",
        t => t,
    }
}
pub fn domain(ty: &str) -> bool {
    matches!(
        ty,
        "Dir" | "Dir8" | "DiagDir" | "Axis" | "DiagAxis" | "Sense" | "C4" | "D4" | "Sym" | "Axis4"
    )
}
pub fn strings(v: &Value, field: &str) -> Result<Vec<String>> {
    v.get(field)
        .and_then(Value::as_array)
        .ok_or_else(|| format!("missing {field}"))?
        .iter()
        .map(|s| {
            s.as_str()
                .map(str::to_owned)
                .ok_or_else(|| format!("non-string {field}"))
        })
        .collect()
}
impl Table {
    pub fn read(v: &Value, work: &mut Work) -> Result<Self> {
        if v.get("fault").is_some_and(|v|!v.is_null()) || v.get("stop").is_some_and(|v|!v.is_null()) {
            return Err("faulted or stopped table".into());
        }
        if v.get("status")
            .and_then(Value::as_str)
            .is_some_and(|s| !matches!(s, "complete" | "determined"))
            || v.get("unseen").and_then(Value::as_bool) == Some(true)
        {
            return Err("incomplete table".into());
        }
        let types = strings(v, "types")?;
        let physical: usize = types.iter().map(|t| width(t)).sum();
        let per = v
            .get("rows")
            .and_then(Value::as_array)
            .ok_or("missing full rows")?;
        if per.is_empty() {
            return Err("no input universe".into());
        }
        let mut rows = Vec::new();
        for input in per {
            let mut set = Rows::new();
            for row in input.as_array().ok_or("missing input rows")? {
                let cells = row.as_array().ok_or("invalid row")?;
                work.charge(physical.max(1))?;
                if cells.len() != physical {
                    return Err("physical row does not match schema".into());
                }
                let mut at = 0;
                let mut logical = Vec::new();
                for ty in &types {
                    let end = at + width(ty);
                    logical.push(
                        cells[at..end]
                            .iter()
                            .map(|c| {
                                c.as_i64()
                                    .and_then(|n| i32::try_from(n).ok())
                                    .ok_or_else(|| "cell is not i32".into())
                            })
                            .collect::<Result<Cell>>()?,
                    );
                    at = end;
                }
                set.insert(logical);
            }
            rows.push(set);
        }
        let names = v
            .get("columns")
            .or_else(|| v.get("names"))
            .and_then(Value::as_array)
            .filter(|a| a.len() == types.len())
            .map(|a| {
                a.iter()
                    .map(|n| n.as_str().unwrap_or("").to_owned())
                    .collect()
            })
            .unwrap_or_else(|| (0..types.len()).map(|i| format!("c{i}")).collect());
        let mut flows = vec![Vec::new(); types.len()];
        if let Some(fs) = v.get("flows").and_then(Value::as_array) {
            if fs.len() != types.len() {
                return Err("flow/schema width mismatch".into());
            }
            for (dst, src) in flows.iter_mut().zip(fs) {
                for f in src.as_array().ok_or("invalid column flows")? {
                    let (kind, table) = if f.is_object() {
                        (f.get("kind"), f.get("source_table"))
                    } else {
                        (f.get(0), f.get(1))
                    };
                    let kind = kind
                        .and_then(Value::as_u64)
                        .filter(|k| *k <= 3)
                        .ok_or("invalid flow kind")? as u8;
                    dst.push((
                        kind,
                        table.and_then(Value::as_i64).ok_or("invalid flow source")?,
                    ));
                }
            }
        }
        let mut meta = v.clone();
        // Keep presentation/context metadata, not a second full row store in
        // every temporary filtered table.
        if let Some(object) = meta.as_object_mut() {
            object.remove("rows");
        }
        Ok(Self {
            types,
            names,
            rows,
            flows,
            meta,
        })
    }
    pub fn json(&self) -> Value {
        let mut v = self.meta.clone();
        v["types"] = json!(self.types);
        v["rows"] = json!(
            self.rows
                .iter()
                .map(|rs| rs
                    .iter()
                    .map(|r| r.iter().flatten().copied().collect::<Vec<_>>())
                    .collect::<Vec<_>>())
                .collect::<Vec<_>>()
        );
        v
    }
    pub fn restrict(&self, inputs: &[usize]) -> Self {
        let mut out = self.clone();
        out.rows = inputs.iter().map(|i| self.rows[*i].clone()).collect();
        out
    }
    pub fn values(&self, col: usize) -> Vec<BTreeSet<Cell>> {
        self.rows
            .iter()
            .map(|rs| rs.iter().map(|r| r[col].clone()).collect())
            .collect()
    }
    pub fn lib(&self, col: usize) -> bool {
        !self.flows[col].is_empty()
            && self.flows[col]
                .iter()
                .all(|(k, t)| (*k == 0 && *t < 0) || matches!(k, 2 | 3))
    }
    pub fn excluded_context(&self) -> bool {
        self.meta.get("relation").and_then(Value::as_str) == Some("ex_output")
            || self.meta.get("table").and_then(Value::as_u64) == Some(1)
    }
}
pub fn project(rows: &Rows, cols: &[usize], work: &mut Work) -> Result<Rows> {
    work.charge(rows.len().saturating_mul(cols.len().max(1)))?;
    Ok(rows
        .iter()
        .map(|r| cols.iter().map(|c| r[*c].clone()).collect())
        .collect())
}
pub fn projected(table: &Table, cols: &[usize], work: &mut Work) -> Result<Vec<Rows>> {
    table.rows.iter().map(|r| project(r, cols, work)).collect()
}
pub fn all_values(t: &Table, c: usize) -> BTreeSet<Cell> {
    t.rows
        .iter()
        .flat_map(|rs| rs.iter().map(|r| r[c].clone()))
        .collect()
}
pub fn unknown(error: String, work: &Work) -> Value {
    json!({"status":"unknown","reason":error,"work":work.used(),"work_cap":work.cap()})
}
pub fn compatible(a: &Value, b: &Value, exclude: &BTreeSet<String>) -> Result<bool> {
    let Some(aa) = a.get("assignment").and_then(Value::as_object) else {
        return Err("missing explicit DET assignment".into());
    };
    let Some(bb) = b.get("assignment").and_then(Value::as_object) else {
        return Err("missing explicit DET assignment".into());
    };
    Ok(aa
        .iter()
        .all(|(k, v)| exclude.contains(k) || bb.get(k).is_none_or(|w| v == w)))
}
pub fn context(v: &Value, target: &Table, work: &mut Work) -> Result<Vec<Table>> {
    let mut out = Vec::new();
    for src in v.as_array().ok_or("context must be an array")? {
        if src.get("used").and_then(Value::as_bool) == Some(false) {
            continue;
        }
        if !compatible(&target.meta, src, &BTreeSet::new())? {
            continue;
        }
        let t = Table::read(src, work)?;
        if t.rows.len() != target.rows.len() {
            return Err("context input universe differs".into());
        }
        out.push(t);
    }
    Ok(out)
}
pub fn combinations(items: &[usize], size: usize, work: &mut Work) -> Result<Vec<Vec<usize>>> {
    fn visit(
        items: &[usize],
        n: usize,
        start: usize,
        prefix: &mut Vec<usize>,
        out: &mut Vec<Vec<usize>>,
        work: &mut Work,
    ) -> Result<()> {
        work.charge(1)?;
        if n == 0 {
            out.push(prefix.clone());
            return Ok(());
        }
        if items.len().saturating_sub(start) < n {
            return Ok(());
        }
        for i in start..=items.len() - n {
            prefix.push(items[i]);
            visit(items, n - 1, i + 1, prefix, out, work)?;
            prefix.pop();
        }
        Ok(())
    }
    let mut out = Vec::new();
    visit(items, size, 0, &mut Vec::new(), &mut out, work)?;
    Ok(out)
}
pub type Map = BTreeMap<Cell, BTreeSet<Cell>>;
