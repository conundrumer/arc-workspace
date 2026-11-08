//! The public packed-term decoder for stored native assignment evidence.
use crate::registry::Registry;
use crate::terms::{Constant, Term, TermId};
use crate::types::ValueType;
use serde_json::{Value, json};

/// The finite encoding domain, distinct from a task-dependent proposal domain.
/// Pose has a nominal assembly identity but Term::decode uses D4 encodings.
pub fn orientation_cells(ty:&ValueType,registry:&Registry)->Option<Vec<i32>> {
    let encoding_type=if matches!(ty,ValueType::Pose(_)) {&ValueType::D4} else {ty};
    let families=encoding_type.orientation_types()?;
    let mut cells=families.iter().flat_map(|of|registry.constants_of(*of).each())
        .filter(|constant|*encoding_type!=ValueType::C4 || registry.c4_constants().contains(*constant))
        .map(|constant|Term::Constant(Constant::Orientation(constant)).encode().expect("registry orientation encodes").encoding() as i32)
        .collect::<Vec<_>>();
    cells.sort_unstable();cells.dedup();Some(cells)
}

pub fn orientation_domain(type_name:&str,registry:&Registry)->Result<Value,String> {
    let ty=scalar_type(type_name)?;
    let cells=orientation_cells(&ty,registry).ok_or_else(||format!("{type_name:?} is not an orientation-valued type"))?;
    Ok(json!({"type":type_name,"encoding_type":format!("{ty:?}"),"cells":cells,
        "constants":cells.iter().map(|cell|decode(type_name,i64::from(*cell),registry)).collect::<Result<Vec<_>,_>>()?,
        "scope":"finite scalar encoding domain; assembly-specific admissibility is evaluated separately"}))
}

pub fn program_orientation_domains(program:&super::StudyProgram,registry:&Registry)->Value {
    fn add(ty:&ValueType,registry:&Registry,out:&mut std::collections::BTreeMap<String,Vec<i32>>) {
        if let Some(cells)=orientation_cells(ty,registry) {out.insert(format!("{ty:?}"),cells);}
        if let ValueType::Record(fields)=ty {for (_,ty) in fields.iter() {add(ty,registry,out);}}
    }
    fn walk(node:crate::program::path::NodeRef<'_>,at:&crate::program::path::NodePath,program:&super::StudyProgram,
        registry:&Registry,out:&mut std::collections::BTreeMap<String,Vec<i32>>) {
        if let Some(form)=program.checked().types.form(at) {
            for (_,ty) in form.labels() {add(ty,registry,out);}
            for (_,columns) in form.relations() {for ty in columns {add(ty,registry,out);}}
        }
        for (i,child) in node.children().into_iter().enumerate() {walk(child,&at.child(i as u32),program,registry,out);}
    }
    let mut domains=std::collections::BTreeMap::new();
    use ValueType::*;
    for ty in [Dir,DiagDir,Dir8,Axis,DiagAxis,Axis4,D4,C4,Sym,Sense] {add(&ty,registry,&mut domains);}
    for (_,columns) in program.checked().types.relations() {for ty in columns {add(ty,registry,&mut domains);}}
    walk(crate::program::path::NodeRef::Program(program.program().value()),&Default::default(),program,registry,&mut domains);
    json!(domains)
}

pub fn scalar_type(name: &str) -> Result<ValueType, String> {
    Ok(match name.to_ascii_lowercase().as_str() {
        "number" | "int" => ValueType::Int,
        "nat" => ValueType::Nat,
        "color" => ValueType::Color,
        "example" => ValueType::Example,
        "unit" => ValueType::Unit,
        "box" => ValueType::Box,
        "position" => ValueType::Position,
        "offset" => ValueType::Offset,
        "ident" => ValueType::OPEN_IDENT,
        "c4" => ValueType::C4,
        "d4" => ValueType::D4,
        "dir" => ValueType::Dir,
        "diagdir" => ValueType::DiagDir,
        "dir8" => ValueType::Dir8,
        "axis" => ValueType::Axis,
        "diagaxis" => ValueType::DiagAxis,
        "axis4" => ValueType::Axis4,
        "sym" => ValueType::Sym,
        "sense" => ValueType::Sense,
        n if n == "pose" || n.starts_with("pose(") => ValueType::D4, // Term::decode(Pose) delegates to D4.
        _ => {
            return Err(format!(
                "unsupported scalar term type {name:?}; flatten records into their typed columns"
            ));
        }
    })
}

pub fn decode(type_name: &str, packed: i64, registry: &Registry) -> Result<Value, String> {
    if packed < i64::from(i32::MIN) || packed > i64::from(u32::MAX) {
        return Err("packed term must fit signed int32 or unsigned u32".into());
    }
    let bits = packed as u32;
    let ty = scalar_type(type_name)?;
    if matches!(ty, ValueType::Color) && bits > 9 {
        return Err("Color term outside ARC colors 0..9".into());
    }
    if matches!(ty, ValueType::Example) && bits > u32::from(u16::MAX) {
        return Err("Example term outside u16".into());
    }
    if matches!(ty, ValueType::Unit) && bits != 0 {
        return Err("Unit term must encode as zero".into());
    }
    if let Some(types) = ty.orientation_types() {
        let admitted = types
            .iter()
            .flat_map(|t| registry.constants_of(*t).each())
            .any(|c| {
                Term::Constant(Constant::Orientation(c))
                    .encode()
                    .is_ok_and(|v| v.encoding() == bits)
                    && (ty != ValueType::C4 || registry.c4_constants().contains(c))
            });
        if !admitted {
            return Err(format!("invalid {type_name} orientation encoding {bits}"));
        }
    }
    // A lib name's cell in a packed row is its export cell, which is no number of this process.
    let id = if matches!(ty, ValueType::LibName) {
        let name = crate::terms::LibNameId::from_export_cell(bits as i32).ok_or_else(|| format!("no lib name of this process has the cell {bits}"))?;
        match Term::Constant(Constant::LibName(name)).encode() {
            Ok(id) => id,
            Err(_) => return Err("a lib name encodes".into()),
        }
    } else {
        TermId::from_encoding(bits)
    };
    let term = Term::decode(id, &ty);
    let value = match term {
        Term::Number(n) => json!({"kind":"number","value":n.0,"pretty":n.0.to_string()}),
        Term::Box(m) => {
            json!({"kind":"box","margins":{"top":m.top,"bottom":m.bottom,"left":m.left,"right":m.right},
            "pretty":format!("(t={} b={} l={} r={})",m.top,m.bottom,m.left,m.right),
            "coordinates":{"status":if ty==ValueType::Offset {"offset"} else {"requires_reference_frame"},
                "row":m.top,"column":m.left,
                "note":"row/column use this value's reference frame; supply its native frame/extent before treating a Box as a cell"}})
        }
        Term::Constant(Constant::Color(c)) => {
            json!({"kind":"color","value":c.digit(),"pretty":c.digit().to_string()})
        }
        Term::Constant(Constant::Example(e)) => {
            json!({"kind":"example","value":e.index(),"pretty":format!("example {}",e.index())})
        }
        Term::Constant(Constant::Unit) => json!({"kind":"unit","pretty":"unit"}),
        Term::Constant(Constant::LibName(name)) => json!({"kind":"lib_name","name":&*name.text(),"pretty":&*name.text()}),
        Term::Constant(Constant::Orientation(c)) => {
            json!({"kind":"orientation","name":registry.constant_name(c),"pretty":registry.constant_name(c)})
        }
        Term::Ident(_) => {
            json!({"kind":"ident","encoding":bits,"opaque":true,"pretty":format!("Ident({bits})"),"meaning":"identity in its native task session"})
        }
    };
    let mut value = value;
    value["type"] = json!(type_name);
    value["encoding_u32"] = json!(bits);
    if type_name.to_ascii_lowercase().starts_with("pose") {
        value["nominal_type"] = json!(type_name);
    }
    Ok(value)
}

/// Whether the reserved decoder label stands at `ty`.
pub fn check_zero(ty: &ValueType) -> Result<(), String> {
    if !ty.has_zero() {
        return Err(format!("reserved zero is illegal at {ty:?}"));
    }
    Ok(())
}

/// Meaning of the reserved decoder label, after native site type resolution.
pub fn zero_meaning(ty: &ValueType) -> Result<Value, String> {
    check_zero(ty)?;
    let meaning = match ty {
        ValueType::Int | ValueType::Nat => "number zero",
        ValueType::Offset => "zero offset: identity translation, all four margins zero",
        ValueType::Position => {
            "zero box at Position type: all four frame margins zero; not a top-left cell coordinate"
        }
        _ => "zero box: all four frame margins zero, edges coincide with the reference frame",
    };
    Ok(
        json!({"kind":"reserved_zero","resolved_type":format!("{ty:?}"),"encoding_u32":0,
        "value":if matches!(ty,ValueType::Int | ValueType::Nat) {json!(0)} else {json!({"top":0,"bottom":0,"left":0,"right":0})},
        "meaning":meaning,"documentation":"engine/docs/study-reserved-zero.md"}),
    )
}
