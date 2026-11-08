//! Equality of native normal forms: a factor permutation, typed column
//! permutations, and one Ident bijection shared across all kept factors.
use super::normal::{Factor, Normal};
use super::*;
use std::sync::Arc;
type Ids = BTreeMap<i32, i32>;

fn same_shape(a: &Factor, b: &Factor) -> bool {
    let mut at = a.types.clone();
    let mut bt = b.types.clone();
    at.sort();
    bt.sort();
    at == bt
        && a.masks == b.masks
        && a.rows.len() == b.rows.len()
        && a.rows.iter().zip(&b.rows).all(|(a, b)| a.len() == b.len())
}
fn join_ids(a: &Row, b: &Row, types: &[String], ids: &Ids) -> Option<Ids> {
    let mut out = ids.clone();
    for ((a, b), ty) in a.iter().zip(b).zip(types) {
        if ty == "Ident" {
            if out.get(&a[0]).is_some_and(|v| *v != b[0])
                || out.iter().any(|(k, v)| *k != a[0] && *v == b[0])
            {
                return None;
            }
            out.insert(a[0], b[0]);
        } else if a != b {
            return None;
        }
    }
    Some(out)
}

#[derive(Clone, Debug)]
pub struct Match {
    pub factors: Vec<(usize, usize, Vec<usize>)>,
    pub identifiers: Ids,
}
impl Match {
    pub fn json(&self) -> Value {
        json!({"factors":self.factors.iter().map(|(a,b,columns)|json!({"mutant_factor":a,"candidate_factor":b,"candidate_columns_in_mutant_order":columns})).collect::<Vec<_>>(),"ident_bijection":self.identifiers.iter().map(|(a,b)|json!([a,b])).collect::<Vec<_>>()})
    }
}

/// Return an explicit isomorphism, or none after an exhaustive search.
/// Numeric Ident IDs are never compared across namespaces or canonicalized
/// independently by factor, which would lose their shared incidence.
pub fn equivalent(a: &Normal, b: &Normal, work: &mut Work) -> Result<Option<Match>> {
    if a.excluded != b.excluded || a.factors.len() != b.factors.len() {
        return Ok(None);
    }
    let mut order: Vec<usize> = (0..a.factors.len()).collect();
    order.sort_by_key(|i| {
        b.factors
            .iter()
            .filter(|f| same_shape(&a.factors[*i], f))
            .count()
    });
    struct Search<'a> {
        a: &'a Normal,
        b: &'a Normal,
        order: Vec<usize>,
    }
    impl Search<'_> {
        fn factors(
            &self,
            depth: usize,
            used: &BTreeSet<usize>,
            ids: &Ids,
            path: &[(usize, usize, Vec<usize>)],
            work: &mut Work,
        ) -> Result<Option<Match>> {
            work.charge(1)?;
            if depth == self.order.len() {
                return Ok(Some(Match {
                    factors: path.to_vec(),
                    identifiers: ids.clone(),
                }));
            }
            let ai = self.order[depth];
            let a = &self.a.factors[ai];
            for (bi, b) in self.b.factors.iter().enumerate() {
                if used.contains(&bi) || !same_shape(a, b) {
                    continue;
                }
                let opts: Vec<Vec<usize>> = a
                    .types
                    .iter()
                    .enumerate()
                    .map(|(i, ty)| {
                        (0..b.types.len())
                            .filter(|j| {
                                if &b.types[*j] != ty {
                                    return false;
                                }
                                let av: Vec<BTreeSet<Cell>> = a
                                    .rows
                                    .iter()
                                    .map(|rs| rs.iter().map(|r| r[i].clone()).collect())
                                    .collect();
                                let bv: Vec<BTreeSet<Cell>> = b
                                    .rows
                                    .iter()
                                    .map(|rs| rs.iter().map(|r| r[*j].clone()).collect())
                                    .collect();
                                if ty == "Ident" {
                                    av.iter().zip(bv).all(|(a, b)| a.len() == b.len())
                                } else {
                                    av == bv
                                }
                            })
                            .collect()
                    })
                    .collect();
                if opts.iter().any(Vec::is_empty) {
                    continue;
                }
                let mut next_used = used.clone();
                next_used.insert(bi);
                if let Some(found) = self.columns(
                    0,
                    &opts,
                    &mut Vec::new(),
                    a,
                    b,
                    ai,
                    bi,
                    depth,
                    &next_used,
                    ids,
                    path,
                    work,
                )? {
                    return Ok(Some(found));
                }
            }
            Ok(None)
        }
        fn columns(
            &self,
            i: usize,
            opts: &[Vec<usize>],
            cols: &mut Vec<usize>,
            a: &Factor,
            b: &Factor,
            ai: usize,
            bi: usize,
            depth: usize,
            used: &BTreeSet<usize>,
            ids: &Ids,
            path: &[(usize, usize, Vec<usize>)],
            work: &mut Work,
        ) -> Result<Option<Match>> {
            work.charge(1)?;
            if i < opts.len() {
                for j in &opts[i] {
                    if cols.contains(j) {
                        continue;
                    }
                    cols.push(*j);
                    if let Some(m) = self.columns(
                        i + 1,
                        opts,
                        cols,
                        a,
                        b,
                        ai,
                        bi,
                        depth,
                        used,
                        ids,
                        path,
                        work,
                    )? {
                        return Ok(Some(m));
                    }
                    cols.pop();
                }
                return Ok(None);
            }
            let mut per = Vec::new();
            for (ar, br) in a.rows.iter().zip(&b.rows) {
                let br = project(br, cols, work)?;
                if !a.types.iter().any(|t| t == "Ident") {
                    if ar != &br {
                        return Ok(None);
                    }
                    continue;
                }
                let br = Arc::new(br);
                let rows = ar
                    .iter()
                    .cloned()
                    .map(|r| (r, Arc::clone(&br)))
                    .collect::<Vec<_>>();
                per.extend(rows);
            }
            // Rows with many literal columns generally have only one match.
            work.charge(
                per.iter()
                    .map(|(_, rs)| rs.len().saturating_mul(a.types.len().max(1)))
                    .sum::<usize>(),
            )?;
            per.sort_by_key(|(r, rs)| {
                rs.iter()
                    .filter(|s| join_ids(r, s, &a.types, ids).is_some())
                    .count()
            });
            let mut next_path = path.to_vec();
            next_path.push((ai, bi, cols.clone()));
            self.rows(0, &per, &a.types, depth, used, ids, &next_path, work)
        }
        fn rows(
            &self,
            i: usize,
            per: &[(Row, Arc<Rows>)],
            types: &[String],
            depth: usize,
            used: &BTreeSet<usize>,
            ids: &Ids,
            path: &[(usize, usize, Vec<usize>)],
            work: &mut Work,
        ) -> Result<Option<Match>> {
            work.charge(1)?;
            if i == per.len() {
                return self.factors(depth + 1, used, ids, path, work);
            }
            let (a, choices) = &per[i];
            for b in choices.iter() {
                work.charge(types.len().max(1))?;
                if let Some(next) = join_ids(a, b, types, ids) {
                    if let Some(found) =
                        self.rows(i + 1, per, types, depth, used, &next, path, work)?
                    {
                        return Ok(Some(found));
                    }
                }
            }
            Ok(None)
        }
    }
    Search { a, b, order }.factors(0, &BTreeSet::new(), &Ids::new(), &[], work)
}

/// Compare against every caller-inventoried available/later-gold table.
/// A separate work budget is supplied per request by the binding;
/// once stopped, remaining candidates are explicitly unknown as well.
pub fn evaluate(mutant: &Value, candidates: &Value, earlier: &Value, work: &mut Work) -> Value {
    let mut prepare = || -> Result<(Table, Normal)> {
        let t = Table::read(mutant, work)?;
        let context = context(earlier, &t, work)?;
        let normal = normal::normalize(&t, &context, work)?;
        Ok((t, normal))
    };
    let (table, normal) = match prepare() {
        Ok(p) => p,
        Err(e) => return unknown(e, work),
    };
    let Some(candidates) = candidates.as_array() else {
        return unknown("candidates must be an array".into(), work);
    };
    let mut comparisons = Vec::new();
    let mut matches = Vec::new();
    let mut any_unknown = false;
    for candidate in candidates {
        let id = candidate.get("id").cloned().unwrap_or(Value::Null);
        let role = candidate.get("role").and_then(Value::as_str).unwrap_or("");
        let mut run = || -> Result<Value> {
            if !matches!(role, "available" | "later_gold") {
                return Err("candidate role must be available or later_gold".into());
            }
            let raw = candidate.get("table").ok_or("candidate needs table")?;
            if !compatible(&table.meta, raw, &BTreeSet::new())? {
                return Ok(json!({"status":"not_applicable","assignment_compatible":false}));
            }
            let t = Table::read(raw, work)?;
            if t.rows.len() != table.rows.len() {
                return Err("candidate input universe differs".into());
            }
            let ctx = context(candidate.get("earlier").unwrap_or(earlier), &t, work)?;
            let other = normal::normalize(&t, &ctx, work)?;
            let found = equivalent(&normal, &other, work)?;
            Ok(
                json!({"status":"determined","assignment_compatible":true,"equal":found.is_some(),"witness":found.map(|m|m.json()),"normal":other.json()}),
            )
        };
        let mut result = match run() {
            Ok(v) => v,
            Err(e) => {
                any_unknown = true;
                unknown(e, work)
            }
        };
        result["id"] = id.clone();
        result["role"] = json!(role);
        if result.get("equal").and_then(Value::as_bool) == Some(true) {
            matches.push(json!({"id":id,"role":role}));
        }
        comparisons.push(result);
    }
    json!({"status":if any_unknown {"unknown"} else {"determined"},"policy":"nf4f-spec-native-v1","normal":normal.json(),"comparisons":comparisons,"matches":matches,"work":work.used(),"work_cap":work.cap()})
}
