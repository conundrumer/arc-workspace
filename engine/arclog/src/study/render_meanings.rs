//! Authored semantic contracts, addressed only by resolved registry identity.
use crate::algebra::geometry::{Edge, Geometry};
use crate::registry::Registry;
use crate::terms::{Constant, Term};
use crate::types::ValueType;
use serde_json::{Value, json};

pub fn catalogue() -> &'static Value {
    static CATALOGUE: std::sync::OnceLock<Value> = std::sync::OnceLock::new();
    CATALOGUE.get_or_init(|| {
        serde_json::from_str(include_str!("../../../lib/study-meanings.json"))
            .expect("committed semantic catalogue is valid JSON")
    })
}

pub fn contract(id: &str, registry: &Registry) -> Value {
    let Some(authored) = catalogue()["entries"].get(id) else {
        return json!({"status":"pending","reason":"no authored semantic contract for this resolved registry ID"});
    };
    let mut contract = authored.clone();
    contract["resolved_id"] = json!(id);
    if id == "lib:Walk" {
        contract["operation"] = json!({"kind":"bounded_successor_walk",
            "inputs":{"successor":{"columns":["p","p_next"],"meaning":"directed successor edges"},
                "steps":{"columns":["N"],"meaning":"requested walk bound"}},
            "output":{"port":"walk","columns":["p0","N","p"],"meaning":"N successor edges take p0 to p"},
            "start_domain":"only members having at least one outgoing successor",
            "bound":"max(0, max steps.N), with empty steps treated as 0",
            "zero_steps":"every start reaches itself at N=0",
            "branching":"all reachable endpoints; duplicates removed at each step",
            "dead_end":"no rows after the reachable set becomes empty",
            "implementation_source":"engine/arclog-constructions/src/ray.rs: Walk::evaluate"});
    }
    if id == "lib:apply" {
        let geometry = Geometry::of(registry);
        let permutations = geometry
            .domain(&ValueType::D4)
            .iter()
            .map(|&d| {
                let g = geometry.element(d);
                let out_to_in = Edge::ALL
                    .iter()
                    .map(|&out| {
                        Edge::ALL
                            .iter()
                            .position(|&source| g.image(source) == out)
                            .expect("D4 permutes edges")
                    })
                    .collect::<Vec<_>>();
                let name = match Term::decode(d, &ValueType::D4) {
                    Term::Constant(Constant::Orientation(c)) => registry.constant_name(c),
                    _ => unreachable!(),
                };
                json!({"D":name,"output_margin_from_input_index":out_to_in})
            })
            .collect::<Vec<_>>();
        contract["operation"] = json!({"kind":"d4_image_of_box_margins","input_columns":["D","P"],"output_column":"P_out",
            "margin_order":["top","bottom","left","right"],"rule":"the margin at each input edge goes to that edge's D4 image",
            "permutations":permutations,"zero_box":"all four margins remain zero under every D4 element",
            "implementation_source":"engine/arclog/src/algebra/boxes.rs: apply; geometry::D4Element::image"});
    }
    contract
}
