//! Native nf4f/spec table normal form. Gold and mutant use this one path.
//! Factors retain their actual typed rows; equality never trusts a hash.
use super::*;
use arclog::program::column_spelled;
use arclog::registry::{LibName, Registry};

#[derive(Clone, Debug)]
pub struct Factor {
    pub types: Vec<String>,
    pub rows: Vec<Rows>,
    pub columns: Vec<usize>,
    pub masks: Vec<(Vec<usize>, usize)>,
}
#[derive(Clone, Debug, Default)]
pub struct Normal {
    pub factors: Vec<Factor>,
    pub removed: Vec<Value>,
    pub excluded: bool,
}
impl Normal {
    pub fn json(&self) -> Value {
        json!({"policy":"nf4f-spec-native-v1","excluded":self.excluded,"empty":self.factors.is_empty(),"removed":self.removed,
        "factors":self.factors.iter().map(|f|json!({"types":f.types,"columns":f.columns,"masks":f.masks,"rows":f.rows.iter().map(|rs|rs.iter().map(|r|r.iter().flatten().copied().collect::<Vec<_>>()).collect::<Vec<_>>()).collect::<Vec<_>>()})).collect::<Vec<_>>()})
    }
}
fn same(t: &Table, cols: &[usize], work: &mut Work) -> Result<bool> {
    let p = projected(t, cols, work)?;
    Ok(!p[0].is_empty() && p.iter().all(|r| r == &p[0]))
}
fn lib_any(t: &Table, c: usize) -> bool {
    !t.flows[c].is_empty() && t.flows[c].iter().all(|(k, s)| *s < 0 || matches!(k, 2 | 3))
}
fn tested(t: &Table, c: usize) -> bool {
    let mut counts: BTreeMap<Cell, usize> = BTreeMap::new();
    for per in t.values(c) {
        for v in per {
            *counts.entry(v).or_default() += 1;
        }
    }
    counts.values().filter(|v| **v >= 2).count() * 2 >= counts.len().max(2)
}
fn pairs(t: &Table, a: usize, b: usize) -> Map {
    let mut out = Map::new();
    for r in t.rows.iter().flatten() {
        out.entry(r[a].clone()).or_default().insert(r[b].clone());
    }
    out
}
fn functional(t: &Table, a: usize, b: usize, work: &mut Work) -> Result<bool> {
    work.charge(t.rows.iter().map(Rows::len).sum::<usize>().max(1))?;
    Ok(pairs(t, a, b).values().all(|v| v.len() == 1))
}

/// Exact projection restatement, repeated source columns allowed. An
/// exhausted work budget is unknown, never a silently truncated search.
pub fn restates(t: &Table, cols: &[usize], earlier: &[Table], work: &mut Work) -> Result<bool> {
    let want = projected(t, cols, work)?;
    for e in earlier.iter().filter(|e| !e.excluded_context()) {
        if e.rows.len() != t.rows.len() {
            return Err("context input universe differs".into());
        }
        if e.rows.iter().zip(&want).any(|(a, b)| a.len() < b.len()) {
            continue;
        }
        let mut opts = Vec::new();
        for c in cols {
            let needed = t.values(*c);
            let matches = (0..e.types.len())
                .filter(|j| e.types[*j] == t.types[*c] && e.values(*j) == needed)
                .collect::<Vec<_>>();
            opts.push(matches);
        }
        fn choose(
            i: usize,
            opts: &[Vec<usize>],
            chosen: &mut Vec<usize>,
            e: &Table,
            want: &[Rows],
            work: &mut Work,
        ) -> Result<bool> {
            work.charge(1)?;
            if i == opts.len() {
                return Ok(projected(e, chosen, work)? == want);
            }
            for c in &opts[i] {
                chosen.push(*c);
                if choose(i + 1, opts, chosen, e, want, work)? {
                    return Ok(true);
                }
                chosen.pop();
            }
            Ok(false)
        }
        if choose(0, &opts, &mut Vec::new(), e, &want, work)? {
            return Ok(true);
        }
    }
    Ok(false)
}
fn earlier_shown(
    t: &Table,
    j: Option<usize>,
    c: usize,
    earlier: &[Table],
    work: &mut Work,
) -> Result<bool> {
    let cols = j.map(|j| vec![j, c]).unwrap_or_else(|| vec![c]);
    let want = projected(t, &cols, work)?;
    let Some(first) = want.iter().find(|r| !r.is_empty()) else {
        return Ok(false);
    };
    for e in earlier.iter().filter(|e| !e.excluded_context()) {
        for v in 0..e.types.len() {
            if e.types[v] != t.types[c] {
                continue;
            }
            if let Some(j) = j {
                for k in 0..e.types.len() {
                    if k == v || e.types[k] != t.types[j] {
                        continue;
                    }
                    work.charge(e.rows.iter().map(Rows::len).sum::<usize>().max(1))?;
                    let pool = pairs(e, k, v);
                    if first
                        .iter()
                        .all(|r| pool.get(&r[0]) == Some(&BTreeSet::from([r[1].clone()])))
                        && !same(e, &[k, v], work)?
                        && tested(e, k)
                    {
                        return Ok(true);
                    }
                }
            } else if e
                .values(v)
                .iter()
                .all(|s| s == &first.iter().map(|r| r[0].clone()).collect())
                && !same(e, &(0..e.types.len()).collect::<Vec<_>>(), work)?
            {
                return Ok(true);
            }
        }
    }
    Ok(false)
}
fn lookup(
    t: &Table,
    c: usize,
    others: &[usize],
    earlier: &[Table],
    work: &mut Work,
) -> Result<Option<usize>> {
    for j in others {
        if t.lib(*j) && !t.lib(c) {
            continue;
        }
        for e in earlier.iter().filter(|e| !e.excluded_context()) {
            for k in 0..e.types.len() {
                if e.types[k] != t.types[*j] {
                    continue;
                }
                for v in 0..e.types.len() {
                    if v == k || e.types[v] != t.types[c] {
                        continue;
                    }
                    work.charge(e.rows.iter().map(Rows::len).sum::<usize>().max(1))?;
                    let per: Vec<Map> = e
                        .rows
                        .iter()
                        .map(|rs| {
                            let mut m = Map::new();
                            for r in rs {
                                m.entry(r[k].clone()).or_default().insert(r[v].clone());
                            }
                            m
                        })
                        .collect();
                    if per.iter().all(|m| m.values().all(|s| s.len() == 1))
                        && t.rows.iter().zip(&per).all(|(rs, m)| {
                            rs.iter()
                                .all(|r| m.get(&r[*j]) == Some(&BTreeSet::from([r[c].clone()])))
                        })
                    {
                        return Ok(Some(*j));
                    }
                    let pool = pairs(e, k, v);
                    if t.rows
                        .iter()
                        .flatten()
                        .all(|r| pool.get(&r[*j]) == Some(&BTreeSet::from([r[c].clone()])))
                    {
                        return Ok(Some(*j));
                    }
                }
            }
        }
    }
    Ok(None)
}
fn factorize(t: &Table, cols: &[usize], work: &mut Work) -> Result<Vec<Vec<usize>>> {
    let mut groups = Vec::new();
    let mut rest = cols.to_vec();
    while !rest.is_empty() {
        let mut found = None;
        'sizes: for size in 0..(rest.len() - 1).min(5) {
            for extra in combinations(&rest[1..], size, work)? {
                let a: Vec<_> = std::iter::once(rest[0]).chain(extra).collect();
                let b: Vec<_> = rest.iter().filter(|c| !a.contains(c)).copied().collect();
                let pa = projected(t, &a, work)?;
                let pb = projected(t, &b, work)?;
                let total = projected(t, &rest, work)?;
                if pa
                    .iter()
                    .zip(&pb)
                    .zip(&total)
                    .all(|((a, b), r)| a.len().checked_mul(b.len()) == Some(r.len()))
                {
                    found = Some(a);
                    break 'sizes;
                }
            }
        }
        match found {
            Some(a) => {
                rest.retain(|c| !a.contains(c));
                groups.push(a);
            }
            None => {
                groups.push(rest);
                break;
            }
        }
    }
    Ok(groups)
}
fn pooled(earlier: &[Table], work: &mut Work) -> Result<Vec<Table>> {
    let mut out = Vec::new();
    for t in earlier.iter().filter(|e| !e.excluded_context()) {
        work.charge(t.rows.iter().map(Rows::len).sum::<usize>().max(1))?;
        let union: Rows = t.rows.iter().flatten().cloned().collect();
        let mut u = t.clone();
        u.rows = vec![union; t.rows.len()];
        out.push(u);
        if !t.types.iter().any(|t| t == "Example") {
            let mut u = t.clone();
            u.types.insert(0, "Example".into());
            let tagged: Rows = t
                .rows
                .iter()
                .enumerate()
                .flat_map(|(i, rs)| {
                    rs.iter()
                        .map(move |r| std::iter::once(vec![i as i32]).chain(r.clone()).collect())
                })
                .collect();
            u.rows = vec![tagged; t.rows.len()];
            out.push(u);
        }
    }
    Ok(out)
}
fn reverse(t: &Table, cols: &[usize], earlier: &[Table], work: &mut Work) -> Result<bool> {
    let want = projected(t, cols, work)?;
    for (position, c) in cols
        .iter()
        .enumerate()
        .filter(|(_, c)| domain(&t.types[**c]))
    {
        for e in earlier.iter().filter(|e| !e.excluded_context()) {
            let opts: Vec<Vec<usize>> = cols
                .iter()
                .map(|col| {
                    (0..e.types.len())
                        .filter(|j| {
                            e.types[*j] == t.types[*col]
                                && (*col == *c || e.values(*j) == t.values(*col))
                        })
                        .collect()
                })
                .collect();
            fn choose(
                depth: usize,
                opts: &[Vec<usize>],
                chosen: &mut Vec<usize>,
                e: &Table,
                want: &[Rows],
                pos: usize,
                work: &mut Work,
            ) -> Result<bool> {
                work.charge(1)?;
                if depth < opts.len() {
                    for j in &opts[depth] {
                        if chosen.contains(j) {
                            continue;
                        }
                        chosen.push(*j);
                        if choose(depth + 1, opts, chosen, e, want, pos, work)? {
                            return Ok(true);
                        }
                        chosen.pop();
                    }
                    return Ok(false);
                }
                let got = projected(e, chosen, work)?;
                let mut sigma: BTreeMap<Cell, BTreeSet<Cell>> = BTreeMap::new();
                for (w, g) in want.iter().zip(&got) {
                    for r in w {
                        work.charge(g.len().max(1))?;
                        let candidates: BTreeSet<Cell> = g
                            .iter()
                            .filter(|s| s.iter().enumerate().all(|(i, v)| i == pos || v == &r[i]))
                            .map(|s| s[pos].clone())
                            .collect();
                        let entry = sigma.entry(r[pos].clone()).or_insert(candidates.clone());
                        *entry = entry.intersection(&candidates).cloned().collect();
                        if entry.is_empty() {
                            return Ok(false);
                        }
                    }
                }
                if sigma.values().any(|s| s.len() != 1) {
                    return Ok(false);
                }
                let map: BTreeMap<Cell, Cell> = sigma
                    .into_iter()
                    .map(|(k, v)| (k, v.into_iter().next().unwrap()))
                    .collect();
                if map.values().collect::<BTreeSet<_>>().len() != map.len()
                    || map.iter().all(|(a, b)| a == b)
                {
                    return Ok(false);
                }
                for (w, g) in want.iter().zip(&got) {
                    let renamed: Rows = w
                        .iter()
                        .map(|r| {
                            let mut r = r.clone();
                            r[pos] = map[&r[pos]].clone();
                            r
                        })
                        .collect();
                    if &renamed != g {
                        return Ok(false);
                    }
                }
                Ok(true)
            }
            if choose(0, &opts, &mut Vec::new(), e, &want, position, work)? {
                return Ok(true);
            }
        }
    }
    Ok(false)
}

fn carried(t: &Table, inputs: &[Table], work: &mut Work) -> Result<BTreeSet<usize>> {
    if let (Some(comp), Some(port)) = (
        t.meta.get("component").and_then(Value::as_str),
        t.meta.get("port").and_then(Value::as_str),
    ) {
        let component =
            arclog::resolver::registry_columns::component(Registry::get(), &LibName(comp.into()))
                .ok_or("unknown component")?;
        let output = component
            .outputs
            .iter()
            .find(|p| p.name.0.as_ref() == port)
            .ok_or("unknown component output")?;
        let copied: BTreeSet<String> = output
            .copies
            .iter()
            .flat_map(|row| row.alternatives.iter())
            .flat_map(|a| {
                a.columns
                    .iter()
                    .map(|(_, j)| column_spelled(&output.columns[*j].name).to_owned())
            })
            .collect();
        if t.meta
            .get("names")
            .or_else(|| t.meta.get("columns"))
            .is_some()
        {
            return Ok(t
                .names
                .iter()
                .enumerate()
                .filter(|(_, n)| {
                    n.split('.')
                        .next()
                        .is_some_and(|p| p == "key" || copied.contains(p))
                })
                .map(|(i, _)| i)
                .collect());
        }
    }
    let mut out = BTreeSet::new();
    for c in 0..t.types.len() {
        if !matches!(t.types[c].as_str(), "Box" | "Position" | "Offset" | "Ident") {
            continue;
        }
        for input in inputs {
            for k in 0..input.types.len() {
                work.charge(1)?;
                if input.types[k] == t.types[c]
                    && t.values(c)
                        .iter()
                        .zip(input.values(k))
                        .all(|(a, b)| a.is_subset(&b))
                {
                    out.insert(c);
                }
            }
        }
    }
    Ok(out)
}
fn degenerate(
    t: &Table,
    earlier: &[Table],
    siblings: &[Table],
    work: &mut Work,
) -> Result<Vec<usize>> {
    let inputs = t
        .meta
        .get("input_relations")
        .and_then(Value::as_array)
        .ok_or("component output needs input_relations from its gold AST")?;
    let inputs: Vec<Table> = earlier
        .iter()
        .filter(|t| !t.excluded_context() && inputs.iter().any(|n| n == &t.meta["relation"]))
        .cloned()
        .collect();
    let cc = carried(t, &inputs, work)?;
    let global: Vec<bool> = (0..t.types.len())
        .map(|c| all_values(t, c).len() == 1)
        .collect();
    let mut sibs = Vec::new();
    for s in siblings {
        if s.meta.get("relation") == t.meta.get("relation") {
            continue;
        }
        let carry = carried(s, &inputs, work)?;
        if (0..s.types.len()).any(|j| s.types[j] != "Example" && !carry.contains(&j)) {
            sibs.push(s.clone());
        }
    }
    let mut deg = Vec::new();
    for (e, rows) in t.rows.iter().enumerate().filter(|(_, r)| !r.is_empty()) {
        let local = t.restrict(&[e]);
        let cols: Vec<usize> = (0..t.types.len())
            .filter(|c| t.types[*c] != "Example" || local.values(*c)[0].len() > 1)
            .collect();
        let contrib: Vec<usize> = cols.iter().filter(|c| !cc.contains(c)).copied().collect();
        let mut free = BTreeSet::new();
        for c in &contrib {
            work.charge(rows.len().max(1))?;
            if global[*c] {
                free.insert(*c);
                continue;
            }
            if cols.iter().any(|d| {
                d != c
                    && t.types[*d] == t.types[*c]
                    && (*d < *c || !contrib.contains(d))
                    && rows.iter().all(|r| r[*d] == r[*c])
            }) {
                free.insert(*c);
                continue;
            }
            if t.types[*c] == "Ident" {
                let rest: Vec<_> = cols
                    .iter()
                    .filter(|d| *d != c && !free.contains(d))
                    .copied()
                    .collect();
                let n = local.values(*c)[0].len();
                let mut together = rest.clone();
                together.push(*c);
                if n == 1
                    || !rest.is_empty()
                        && project(rows, &rest, work)?.len() == n
                        && project(rows, &together, work)?.len() == n
                {
                    free.insert(*c);
                }
            }
        }
        let left: Vec<_> = cols.iter().filter(|c| !free.contains(c)).copied().collect();
        let ins: Vec<_> = inputs.iter().map(|t| t.restrict(&[e])).collect();
        let sib: Vec<_> = sibs.iter().map(|t| t.restrict(&[e])).collect();
        if cols.is_empty()
            || !contrib.is_empty() && free.len() == contrib.len()
            || !left.is_empty()
                && (restates(&local, &left, &ins, work)?
                    || contrib.is_empty() && restates(&local, &left, &sib, work)?)
        {
            deg.push(e);
        }
    }
    Ok(deg)
}

pub fn normalize(t: &Table, earlier: &[Table], work: &mut Work) -> Result<Normal> {
    normalize_in(t, earlier, work, true)
}

/// The same table rules at a search point, without whole-program use or
/// component-sibling evidence. No future-dependent exclusion is performed.
pub fn normalize_prefix(t: &Table, earlier: &[Table], work: &mut Work) -> Result<Normal> {
    normalize_in(t, earlier, work, false)
}

fn normalize_in(t: &Table, earlier: &[Table], work: &mut Work, whole_program: bool) -> Result<Normal> {
    let original = t;
    let head = t
        .meta
        .get("head")
        .and_then(Value::as_str)
        .ok_or("normalization needs the original AST form head")?;
    if t.meta.get("flows").and_then(Value::as_array).is_none() {
        return Err("normalization needs explicit native column flows".into());
    }
    if whole_program && t.meta.get("used").and_then(Value::as_bool) == Some(false) {
        return Ok(Normal {
            excluded: true,
            ..Normal::default()
        });
    }
    let mut t = t.clone();
    let mut earlier = earlier.to_vec();
    let mut masks = Vec::new();
    let mut removed = Vec::new();
    if whole_program && head == "INIT"
        && t.meta.get("component").is_some()
        && !(t.meta["component"] == "Enclosure" && t.meta["port"] == "enclosed")
    {
        let sibs = context(
            t.meta
                .get("siblings")
                .ok_or("component output needs its sibling inventory (possibly empty)")?,
            &t,
            work,
        )?;
        let deg = degenerate(&t, &earlier, &sibs, work)?;
        if !deg.is_empty() {
            let keep: Vec<_> = (0..t.rows.len()).filter(|e| !deg.contains(e)).collect();
            removed.push(json!({"rule":"component-degenerate","inputs":deg}));
            masks.push((deg, t.rows.len()));
            t = t.restrict(&keep);
            earlier = earlier.iter().map(|e| e.restrict(&keep)).collect();
        }
    }
    if t.rows.is_empty() || t.rows.iter().all(Rows::is_empty) {
        return Ok(Normal {
            removed,
            ..Normal::default()
        });
    }
    let nz: Vec<_> = t
        .rows
        .iter()
        .enumerate()
        .filter(|(_, r)| !r.is_empty())
        .map(|(i, _)| i)
        .collect();
    if nz.len() < t.rows.len()
        && earlier.iter().any(|e| {
            e.rows
                .iter()
                .enumerate()
                .filter(|(_, r)| !r.is_empty())
                .map(|(i, _)| i)
                .collect::<Vec<_>>()
                == nz
        })
    {
        masks.push((nz.clone(), t.rows.len()));
        removed.push(json!({"rule":"inputs","inputs":nz}));
        t = t.restrict(&nz);
        earlier = earlier.iter().map(|e| e.restrict(&nz)).collect();
    }
    let mut left = Vec::new();
    for c in 0..t.types.len() {
        let vals = t.values(c);
        let reason = if t.types[c] == "Example"
            && vals.iter().filter(|v| !v.is_empty()).all(|v| v.len() == 1)
        {
            Some("example-key")
        } else if all_values(&t, c).len() == 1
            && !t.flows[c].is_empty()
            && t.flows[c].iter().all(|(k, _)| *k == 2)
        {
            Some("program-constant")
        } else if left
            .iter()
            .any(|j| t.types[*j] == t.types[c] && t.rows.iter().flatten().all(|r| r[*j] == r[c]))
        {
            Some("duplicate")
        } else {
            None
        };
        if let Some(rule) = reason {
            removed.push(json!({"column":c,"rule":rule}));
        } else {
            left.push(c);
        }
    }
    let wide = matches!(head, "DET" | "RIGID_DET") && same(&t, &left, work)?;
    let nonconst = left.iter().any(|c| all_values(&t, *c).len() > 1);
    let mut dropped = BTreeSet::new();
    let mut strict = BTreeSet::new();
    if left.len() > 1 {
        for c in &left {
            if all_values(&t, *c).len() == 1
                && nonconst
                && (!wide || earlier_shown(&t, None, *c, &earlier, work)?)
            {
                dropped.insert(*c);
                removed.push(json!({"column":c,"rule":"determined:const"}));
            }
        }
        for c in &left {
            if dropped.contains(c) {
                continue;
            }
            let others: Vec<_> = left
                .iter()
                .filter(|j| *j != c && !dropped.contains(j))
                .copied()
                .collect();
            if others.is_empty() {
                continue;
            }
            let mut via = None;
            let mut rule = "";
            if t.lib(*c) || t.types[*c] != "Color" {
                for j in &others {
                    if domain(&t.types[*j])
                        && tested(&t, *j)
                        && (!t.lib(*j) || t.lib(*c))
                        && functional(&t, *j, *c, work)?
                        && (!wide || earlier_shown(&t, Some(*j), *c, &earlier, work)?)
                    {
                        via = Some(*j);
                        rule = if t.lib(*c) {
                            "determined:lib"
                        } else {
                            "determined:domain-map"
                        };
                        break;
                    }
                }
            }
            if via.is_none() {
                via = lookup(&t, *c, &others, &earlier, work)?;
                rule = "lookup";
            }
            if let Some(j) = via {
                dropped.insert(*c);
                if !t.lib(*c) {
                    strict.insert(j);
                }
                removed.push(json!({"column":c,"rule":rule,"via":j}));
            }
        }
    }
    left.retain(|c| !dropped.contains(c));
    let mut groups = factorize(&t, &left, work)?;
    if left.is_empty() && t.rows.iter().any(Rows::is_empty) {
        groups.push(Vec::new());
    }
    let mut factors = Vec::new();
    let mut pool = None;
    for cols in groups {
        let rs = projected(&t, &cols, work)?;
        let identical = !rs[0].is_empty() && rs.iter().all(|r| r == &rs[0]);
        let enum_one = cols.len() == 1
            && domain(&t.types[cols[0]])
            && t.values(cols[0]).iter().any(|v| v.len() > 1)
            && (lib_any(&t, cols[0]) || identical);
        let rule = if restates(&t, &cols, &earlier, work)? {
            Some("restatement")
        } else if enum_one && (!cols.iter().any(|c| strict.contains(c)) || identical) {
            Some("domain")
        } else if cols.len() >= 2 && cols.iter().all(|c| domain(&t.types[*c])) && identical {
            Some("product-domain")
        } else {
            let mut rule = None;
            if !cols.is_empty() && identical {
                if pool.is_none() {
                    pool = Some(pooled(&earlier, work)?);
                }
                if restates(&t, &cols, pool.as_ref().unwrap(), work)? {
                    rule = Some("pooled");
                }
            }
            if rule.is_none() && !cols.is_empty() && reverse(&t, &cols, &earlier, work)? {
                rule = Some("reverse");
            }
            if rule.is_none()
                && head != "DET"
                && !cols.is_empty()
                    && cols.iter().all(|c| lib_any(original, *c))
                    && same(original, &cols, work)?
            {
                rule = Some("lib-constant");
            }
            rule
        };
        if let Some(rule) = rule {
            removed.push(json!({"columns":cols,"rule":rule}));
        } else {
            factors.push(Factor {
                types: cols.iter().map(|c| t.types[*c].clone()).collect(),
                rows: rs,
                columns: cols,
                masks: masks.clone(),
            });
        }
    }
    Ok(Normal {
        factors,
        removed,
        excluded: false,
    })
}
pub fn evaluate(table: &Value, earlier: &Value, work: &mut Work) -> Value {
    evaluate_in(table, earlier, work, true)
}

pub fn evaluate_prefix(table: &Value, earlier: &Value, work: &mut Work) -> Value {
    evaluate_in(table, earlier, work, false)
}

fn evaluate_in(table: &Value, earlier: &Value, work: &mut Work, whole_program: bool) -> Value {
    let mut run = || -> Result<Value> {
        let t = Table::read(table, work)?;
        let earlier = context(earlier, &t, work)?;
        let mut result = if whole_program { normalize(&t, &earlier, work)? } else { normalize_prefix(&t, &earlier, work)? }.json();
        if !whole_program { result["scope"] = json!("prefix_only"); }
        Ok(result)
    };
    match run() {
        Ok(mut v) => {
            v["status"] = json!("determined");
            v["work"] = json!(work.used());
            v["work_cap"] = json!(work.cap());
            v
        }
        Err(e) => unknown(e, work),
    }
}
