//! Dropped-filter recovery: typed comparisons and one available-table
//! semijoin/antijoin, optionally followed by the equality selection and
//! projection of the original recovery operation.
use super::*;

pub fn finish(mut result: Value, final_output: bool, work: &Work) -> Value {
    let proven = result.get("recoverable").and_then(Value::as_bool) == Some(true);
    result["code_label"] = if proven {
        json!(if final_output { "WRONG" } else { "DETOUR" })
    } else {
        Value::Null
    };
    result["judge_eligible"] = if proven {
        json!(false)
    } else if result["status"] == "unknown" {
        Value::Null
    } else {
        json!(true)
    };
    result["work"] = json!(work.used());
    result["work_cap"] = json!(work.cap());
    result
}
fn witness(
    g: &Table,
    m: &Table,
    filtered: &Table,
    restriction: Value,
    domains: &Value,
    work: &mut Work,
) -> Result<Option<Value>> {
    if let Some(w) = recovery::recover(g, filtered, domains, work)? {
        let evidence=g.rows.iter().zip(&m.rows).zip(&filtered.rows).enumerate().map(|(i,((g,m),f))|json!({"train":i+1,"gold_rows":g.len(),"mutant_rows":m.len(),"restricted_rows":f.len()})).collect::<Vec<_>>();
        return Ok(Some(
            json!({"status":"determined","assignment_compatible":true,"recoverable":true,"verified":true,
            "witness":{"restriction":restriction,"projection":w.projection,"selection":w.selection.iter().map(|p|match p {recovery::Predicate::Constant(c,v)=>json!({"kind":"column_constant","column":c,"value":v}),recovery::Predicate::Equal(a,b)=>json!({"kind":"columns_equal","left":a,"right":b})}).collect::<Vec<_>>()},"inputs":evidence}),
        ));
    }
    Ok(None)
}
fn compare(a: &Cell, b: &Cell, op: &str) -> bool {
    match op {
        "=" => a == b,
        "!=" => a != b,
        "<" => a[0] < b[0],
        "<=" => a[0] <= b[0],
        ">" => a[0] > b[0],
        ">=" => a[0] >= b[0],
        _ => unreachable!(),
    }
}
fn comparisons(g: &Table, m: &Table, domains: &Value, work: &mut Work) -> Result<Option<Value>> {
    let mut seen: BTreeSet<Vec<Rows>> = BTreeSet::new();
    for left in 0..m.types.len() {
        let ordered = recovery_type(&m.types[left]) == "Number";
        let ops: Vec<&str> = if ordered {
            vec!["=", "!=", "<", "<=", ">", ">="]
        } else {
            vec!["=", "!="]
        };
        let mut constants = all_values(m, left);
        for (c, ty) in g.types.iter().enumerate() {
            if recovery_type(ty) == recovery_type(&m.types[left]) {
                constants.extend(all_values(g, c));
            }
        }
        for op in ops {
            for right in 0..m.types.len() {
                if right == left || recovery_type(&m.types[left]) != recovery_type(&m.types[right])
                {
                    continue;
                }
                let mut filtered = m.clone();
                filtered.rows = m
                    .rows
                    .iter()
                    .map(|rs| {
                        work.charge(rs.len().max(1))?;
                        Ok(rs
                            .iter()
                            .filter(|r| compare(&r[left], &r[right], op))
                            .cloned()
                            .collect())
                    })
                    .collect::<Result<_>>()?;
                if filtered.rows == m.rows || !seen.insert(filtered.rows.clone()) {
                    continue;
                }
                let restriction = json!({"kind":"comparison","left":left,"left_name":m.names[left],"operator":op,"right":{"column":right,"name":m.names[right]},"type":recovery_type(&m.types[left])});
                if let Some(w) = witness(g, m, &filtered, restriction, domains, work)? {
                    return Ok(Some(w));
                }
            }
            for value in &constants {
                let mut filtered = m.clone();
                filtered.rows = m
                    .rows
                    .iter()
                    .map(|rs| {
                        work.charge(rs.len().max(1))?;
                        Ok(rs
                            .iter()
                            .filter(|r| compare(&r[left], value, op))
                            .cloned()
                            .collect())
                    })
                    .collect::<Result<_>>()?;
                if filtered.rows == m.rows || !seen.insert(filtered.rows.clone()) {
                    continue;
                }
                let restriction = json!({"kind":"comparison","left":left,"left_name":m.names[left],"operator":op,"right":{"value":value},"type":recovery_type(&m.types[left])});
                if let Some(w) = witness(g, m, &filtered, restriction, domains, work)? {
                    return Ok(Some(w));
                }
            }
        }
    }
    Ok(None)
}

fn semijoins(
    g: &Table,
    m: &Table,
    available: &Value,
    domains: &Value,
    work: &mut Work,
) -> Result<(Option<Value>, Vec<Value>)> {
    let available = available
        .as_array()
        .ok_or("available tables must be an array")?;
    let mut unknowns = Vec::new();
    for candidate in available {
        let id = candidate
            .get("id")
            .ok_or("available table needs an AST id")?;
        if candidate.get("role").and_then(Value::as_str) != Some("available") {
            return Err("semijoin source must have role available, never later_gold".into());
        }
        let raw = candidate
            .get("table")
            .ok_or("available candidate needs table")?;
        match compatible(&m.meta, raw, &BTreeSet::new()) {
            Ok(false) => continue,
            Ok(true) => {}
            Err(e) => {
                unknowns.push(json!({"id":id,"reason":e}));
                continue;
            }
        }
        let source = match Table::read(raw, work) {
            Ok(t) => t,
            Err(e) if !e.starts_with("stopped:") => {
                unknowns.push(json!({"id":id,"reason":e}));
                continue;
            }
            Err(e) => return Err(e),
        };
        if source.rows.len() != m.rows.len() {
            return Err("available table input universe differs".into());
        }
        // A source may depend on fewer DETs, but not on an unassigned DET
        // extension. The caller can supply the full kept assignment here.
        let kept = m
            .meta
            .get("kept_assignment")
            .unwrap_or(&m.meta["assignment"]);
        if let Some(asg) = source.meta.get("assignment").and_then(Value::as_object) {
            if asg.iter().any(|(k, v)| kept.get(k).is_none_or(|w| w != v)) {
                unknowns.push(json!({"id":id,"reason":"source has no value under the full kept DET assignment"}));
                continue;
            }
        }
        let columns: Vec<_> = (0..source.types.len()).collect();
        let mut seen = BTreeSet::new();
        struct Join<'a> {
            g: &'a Table,
            m: &'a Table,
            s: &'a Table,
            id: &'a Value,
            domains: &'a Value,
        }
        impl Join<'_> {
            fn mappings(
                &self,
                cols: &[usize],
                at: usize,
                mapping: &mut Vec<usize>,
                seen: &mut BTreeSet<Vec<Rows>>,
                work: &mut Work,
            ) -> Result<Option<Value>> {
                work.charge(1)?;
                if at < cols.len() {
                    for c in 0..self.m.types.len() {
                        if recovery_type(&self.m.types[c]) != recovery_type(&self.s.types[cols[at]])
                        {
                            continue;
                        }
                        mapping.push(c);
                        if let Some(w) = self.mappings(cols, at + 1, mapping, seen, work)? {
                            return Ok(Some(w));
                        }
                        mapping.pop();
                    }
                    return Ok(None);
                }
                let keys = projected(self.s, cols, work)?;
                for anti in [false, true] {
                    let mut filtered = self.m.clone();
                    filtered.rows = self
                        .m
                        .rows
                        .iter()
                        .zip(&keys)
                        .map(|(rs, ks)| {
                            work.charge(rs.len().saturating_mul(mapping.len().max(1)))?;
                            Ok(rs
                                .iter()
                                .filter(|r| {
                                    ks.contains(
                                        &mapping.iter().map(|c| r[*c].clone()).collect::<Row>(),
                                    ) != anti
                                })
                                .cloned()
                                .collect())
                        })
                        .collect::<Result<_>>()?;
                    if filtered.rows == self.m.rows || !seen.insert(filtered.rows.clone()) {
                        continue;
                    }
                    let restriction = json!({"kind":if anti {"antijoin"} else {"semijoin"},"available_id":self.id,
                        "keys":mapping.iter().zip(cols).map(|(m,s)|json!({"mutant_column":m,"mutant_name":self.m.names[*m],"available_column":s,"available_name":self.s.names[*s],"type":recovery_type(&self.m.types[*m])})).collect::<Vec<_>>()});
                    if let Some(w) =
                        witness(self.g, self.m, &filtered, restriction, self.domains, work)?
                    {
                        return Ok(Some(w));
                    }
                }
                Ok(None)
            }
        }
        let join = Join {
            g,
            m,
            s: &source,
            id,
            domains,
        };
        for size in 0..=columns.len() {
            for cols in combinations(&columns, size, work)? {
                if let Some(w) = join.mappings(&cols, 0, &mut Vec::new(), &mut seen, work)? {
                    return Ok((Some(w), unknowns));
                }
            }
        }
    }
    Ok((None, unknowns))
}

pub fn evaluate(
    g: &Value,
    m: &Value,
    n_train: usize,
    domains: &Value,
    available: &Value,
    final_output: bool,
    work: &mut Work,
) -> Value {
    let base = recovery::evaluate(g, m, n_train, domains, work);
    if base["recoverable"] == true || base["status"] != "determined" {
        return finish(base, final_output, work);
    }
    let mut run = || -> Result<Value> {
        let inputs: Vec<_> = (0..n_train).collect();
        let gold = Table::read(g, work)?.restrict(&inputs);
        let mutant = Table::read(m, work)?.restrict(&inputs);
        if let Some(w) = comparisons(&gold, &mutant, domains, work)? {
            return Ok(w);
        }
        // Recovery uses train rows only; retain each source's full assignment
        // metadata while dropping its held-out input rows.
        let mut sources = available.clone();
        for source in sources
            .as_array_mut()
            .ok_or("available tables must be an array")?
        {
            if let Some(rows) = source
                .get_mut("table")
                .and_then(|t| t.get_mut("rows"))
                .and_then(Value::as_array_mut)
            {
                if rows.len() < n_train {
                    return Err("available table missing train input".into());
                }
                rows.truncate(n_train);
            }
        }
        let (found, unknowns) = semijoins(&gold, &mutant, &sources, domains, work)?;
        Ok(found.unwrap_or_else(||if unknowns.is_empty() {base.clone()} else {json!({"status":"unknown","recoverable":null,"reason":"incomplete available-table coverage","available_unknowns":unknowns})}))
    };
    let result = match run() {
        Ok(v) => v,
        Err(e) => unknown(e, work),
    };
    finish(result, final_output, work)
}
