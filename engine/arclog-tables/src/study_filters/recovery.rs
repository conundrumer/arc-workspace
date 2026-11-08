//! Exact finite equality-selection/projection recovery, matching judge2's
//! row_recovery policy. Search is bounded explicitly, never approximately.
use super::*;

#[derive(Clone, Debug)]
pub enum Predicate {
    Constant(usize, Cell),
    Equal(usize, usize),
}
impl Predicate {
    fn holds(&self, r: &Row) -> bool {
        match self {
            Self::Constant(c, v) => r[*c] == *v,
            Self::Equal(a, b) => r[*a] == r[*b],
        }
    }
    fn json(&self) -> Value {
        match self {
            Self::Constant(c, v) => json!({"kind":"column_constant","column":c,"value":v}),
            Self::Equal(a, b) => json!({"kind":"columns_equal","left":a,"right":b}),
        }
    }
}
#[derive(Clone, Debug)]
pub struct Witness {
    pub projection: Vec<usize>,
    pub selection: Vec<Predicate>,
}
impl Witness {
    pub fn json(&self, gold: &Table, mutant: &Table) -> Value {
        json!({"projection":self.projection,"selection":self.selection.iter().map(Predicate::json).collect::<Vec<_>>(),
            "projection_named":gold.names.iter().zip(&self.projection).map(|(g,m)|json!({"gold_column":g,"mutant_column":mutant.names[*m]})).collect::<Vec<_>>()})
    }
}
type Bits = BTreeSet<usize>;
fn intersection(a: &Bits, b: &Bits, work: &mut Work) -> Result<Bits> {
    work.charge(a.len().min(b.len()).max(1))?;
    Ok(a.intersection(b).copied().collect())
}

fn selection(
    g: &Table,
    m: &Table,
    projection: &[usize],
    domains: &Value,
    work: &mut Work,
) -> Result<Option<Vec<Predicate>>> {
    let mut flat = Vec::new();
    let mut bad = Bits::new();
    let mut targets = Vec::new();
    for (gold, mutant) in g.rows.iter().zip(&m.rows) {
        let mut groups: BTreeMap<Row, Bits> =
            gold.iter().cloned().map(|r| (r, Bits::new())).collect();
        for row in mutant {
            work.charge(projection.len().max(1))?;
            let i = flat.len();
            flat.push(row);
            let projected: Row = projection.iter().map(|c| row[*c].clone()).collect();
            if let Some(group) = groups.get_mut(&projected) {
                group.insert(i);
            } else {
                bad.insert(i);
            }
        }
        if groups.values().any(Bits::is_empty) {
            return Ok(None);
        }
        targets.extend(groups.into_values());
    }
    if bad.is_empty() {
        return Ok(Some(Vec::new()));
    }
    if targets.is_empty() {
        for (col, ty) in m.types.iter().enumerate() {
            let values = match recovery_type(ty) {
                "Box" => vec![vec![0, 0, 0, 0], vec![1, 0, 0, 0]],
                "Offset" => vec![vec![0, 0, 0, 0], vec![1, -1, 0, 0]],
                "Color" | "Number" | "Ident" | "Example" => vec![vec![0], vec![1]],
                t => domains
                    .get(t)
                    .and_then(Value::as_array)
                    .map(|vs| {
                        vs.iter()
                            .filter_map(|v| v.as_i64().and_then(|n| i32::try_from(n).ok()))
                            .map(|n| vec![n])
                            .take(2)
                            .collect()
                    })
                    .unwrap_or_default(),
            };
            if values.len() == 2 && values[0] != values[1] {
                return Ok(Some(
                    values
                        .into_iter()
                        .map(|v| Predicate::Constant(col, v))
                        .collect(),
                ));
            }
        }
        return Ok(None);
    }
    let mut atoms: Vec<(Predicate, Bits)> = Vec::new();
    let mut add = |p: Predicate, work: &mut Work| -> Result<()> {
        work.charge(flat.len().max(1))?;
        let mask: Bits = flat
            .iter()
            .enumerate()
            .filter(|(_, r)| p.holds(r))
            .map(|(i, _)| i)
            .collect();
        if !bad.is_subset(&mask)
            && targets.iter().all(|g| !g.is_disjoint(&mask))
            && !atoms.iter().any(|(_, m)| m == &mask)
        {
            atoms.push((p, mask));
        }
        Ok(())
    };
    for col in 0..m.types.len() {
        let mut values: Option<BTreeSet<Cell>> = None;
        for group in &targets {
            work.charge(group.len().max(1))?;
            let here = group.iter().map(|i| flat[*i][col].clone()).collect();
            values = Some(match values {
                None => here,
                Some(v) => v.intersection(&here).cloned().collect(),
            });
            if values.as_ref().is_some_and(BTreeSet::is_empty) {
                break;
            }
        }
        for value in values.unwrap_or_default() {
            add(Predicate::Constant(col, value), work)?;
        }
    }
    for a in 0..m.types.len() {
        for b in a + 1..m.types.len() {
            if recovery_type(&m.types[a]) == recovery_type(&m.types[b]) {
                add(Predicate::Equal(a, b), work)?;
            }
        }
    }
    let all: Bits = (0..flat.len()).collect();
    fn search(
        allowed: Bits,
        bad: &Bits,
        targets: &[Bits],
        atoms: &[(Predicate, Bits)],
        seen: &mut BTreeSet<Bits>,
        work: &mut Work,
    ) -> Result<Option<Vec<Predicate>>> {
        work.charge(1)?;
        let remaining = intersection(&allowed, bad, work)?;
        let Some(bit) = remaining.first() else {
            return Ok(Some(Vec::new()));
        };
        if !seen.insert(allowed.clone()) {
            return Ok(None);
        }
        let mut choices = Vec::new();
        for (p, mask) in atoms {
            if mask.contains(bit) {
                continue;
            }
            let next = intersection(&allowed, mask, work)?;
            if targets.iter().all(|g| !next.is_disjoint(g)) {
                choices.push((intersection(&remaining, mask, work)?.len(), p, next));
            }
        }
        choices.sort_by_key(|(n, _, _)| *n);
        for (_, p, next) in choices {
            if let Some(mut tail) = search(next, bad, targets, atoms, seen, work)? {
                tail.insert(0, p.clone());
                return Ok(Some(tail));
            }
        }
        Ok(None)
    }
    search(all, &bad, &targets, &atoms, &mut BTreeSet::new(), work)
}

pub fn recover(
    gold: &Table,
    mutant: &Table,
    domains: &Value,
    work: &mut Work,
) -> Result<Option<Witness>> {
    if gold.rows.len() != mutant.rows.len() {
        return Err("input universes differ".into());
    }
    let mut candidates = Vec::new();
    for (c, ty) in gold.types.iter().enumerate() {
        let needed = gold.values(c);
        let mut choices = Vec::new();
        let mut seen = BTreeSet::new();
        for (j, mty) in mutant.types.iter().enumerate() {
            if recovery_type(ty) != recovery_type(mty) {
                continue;
            }
            let got = mutant.values(j);
            work.charge(got.iter().map(BTreeSet::len).sum::<usize>().max(1))?;
            // Deduplicate only literally identical columns in their row
            // contexts, not columns with merely equal marginal value sets.
            let signature: Vec<Vec<Cell>> = mutant
                .rows
                .iter()
                .map(|rs| rs.iter().map(|r| r[j].clone()).collect())
                .collect();
            if !seen.insert(signature) {
                continue;
            }
            if needed.iter().zip(&got).all(|(a, b)| a.is_subset(b)) {
                choices.push(j);
            }
        }
        if choices.is_empty() {
            return Ok(None);
        }
        candidates.push(choices);
    }
    let mut order: Vec<usize> = (0..gold.types.len()).collect();
    order.sort_by_key(|c| candidates[*c].len());
    let mut mapping = vec![0; order.len()];
    fn visit(
        depth: usize,
        order: &[usize],
        candidates: &[Vec<usize>],
        mapping: &mut Vec<usize>,
        g: &Table,
        m: &Table,
        domains: &Value,
        work: &mut Work,
    ) -> Result<Option<Witness>> {
        work.charge(1)?;
        if depth == order.len() {
            return Ok(
                selection(g, m, mapping, domains, work)?.map(|selection| Witness {
                    projection: mapping.clone(),
                    selection,
                }),
            );
        }
        let c = order[depth];
        for mc in &candidates[c] {
            mapping[c] = *mc;
            let gc = &order[..=depth];
            let mapped: Vec<usize> = gc.iter().map(|c| mapping[*c]).collect();
            let want = projected(g, gc, work)?;
            let got = projected(m, &mapped, work)?;
            if want.iter().zip(&got).all(|(a, b)| a.is_subset(b)) {
                if let Some(w) = visit(depth + 1, order, candidates, mapping, g, m, domains, work)?
                {
                    return Ok(Some(w));
                }
            }
        }
        Ok(None)
    }
    let result = visit(
        0,
        &order,
        &candidates,
        &mut mapping,
        gold,
        mutant,
        domains,
        work,
    )?;
    if let Some(w) = &result {
        if !verify(gold, mutant, w, work)? {
            return Err("recovery witness invariant".into());
        }
    }
    Ok(result)
}
pub fn verify(gold: &Table, mutant: &Table, w: &Witness, work: &mut Work) -> Result<bool> {
    for (g, m) in gold.rows.iter().zip(&mutant.rows) {
        work.charge(m.len().saturating_mul(w.selection.len().max(1)))?;
        let kept = m
            .iter()
            .filter(|r| w.selection.iter().all(|p| p.holds(r)))
            .cloned()
            .collect();
        if &project(&kept, &w.projection, work)? != g {
            return Ok(false);
        }
    }
    Ok(true)
}

pub fn evaluate(g: &Value, m: &Value, n_train: usize, domains: &Value, work: &mut Work) -> Value {
    let run = || -> Result<Value> {
        if n_train == 0 {
            return Err("empty train universe".into());
        }
        let gold = Table::read(g, work)?;
        let mutant = Table::read(m, work)?;
        if gold.rows.len() < n_train || mutant.rows.len() < n_train {
            return Err("missing train input".into());
        }
        let inputs: Vec<_> = (0..n_train).collect();
        let gold = gold.restrict(&inputs);
        let mutant = mutant.restrict(&inputs);
        // Values, not local DET assignment indices. The current form's own
        // result can be excluded explicitly, as in the previous policy.
        let exclude = [g, m]
            .into_iter()
            .filter_map(|v| v.get("current_relations").and_then(Value::as_array))
            .flatten()
            .filter_map(Value::as_str)
            .map(str::to_owned)
            .collect();
        if !compatible(g, m, &exclude)? {
            return Ok(json!({"status":"not_applicable","assignment_compatible":false}));
        }
        let result = recover(&gold, &mutant, domains, work)?;
        Ok(match result {
            Some(w) => {
                json!({"status":"determined","assignment_compatible":true,"recoverable":true,"witness":w.json(&gold,&mutant),"verified":true})
            }
            None => {
                json!({"status":"determined","assignment_compatible":true,"recoverable":false,"witness":null})
            }
        })
    };
    let mut run = run;
    match run() {
        Ok(mut value) => {
            value["work"] = json!(work.used());
            value["work_cap"] = json!(work.cap());
            value
        }
        Err(e) => unknown(e, work),
    }
}
