//! The public packed-term decoder for stored native assignment evidence.
use crate::registry::Registry;
use crate::terms::{Constant, Term, TermId};
use crate::types::ValueType;
use serde_json::{Value, json};

pub fn scalar_type(name: &str) -> Result<ValueType, String> {
    Ok(match name.to_ascii_lowercase().as_str() {
        "number" => ValueType::Number,
        "color" => ValueType::Color,
        "example" => ValueType::Example,
        "unit" => ValueType::Unit,
        "box" => ValueType::Box,
        "position" => ValueType::Position,
        "offset" => ValueType::Offset,
        "ident" => ValueType::Ident,
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
    let term = Term::decode(TermId::from_encoding(bits), &ty);
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

/// Meaning of the reserved decoder label, after native site type resolution.
pub fn zero_meaning(ty: &ValueType) -> Result<Value, String> {
    if !ty.has_zero() {
        return Err(format!("reserved zero is illegal at {ty:?}"));
    }
    let meaning = match ty {
        ValueType::Number => "number zero",
        ValueType::Offset => "zero offset: identity translation, all four margins zero",
        ValueType::Position => {
            "zero box at Position type: all four frame margins zero; not a top-left cell coordinate"
        }
        _ => "zero box: all four frame margins zero, edges coincide with the reference frame",
    };
    Ok(
        json!({"kind":"reserved_zero","resolved_type":format!("{ty:?}"),"encoding_u32":0,
        "value":if *ty==ValueType::Number {json!(0)} else {json!({"top":0,"bottom":0,"left":0,"right":0})},
        "meaning":meaning,"documentation":"engine/docs/study-reserved-zero.md"}),
    )
}
