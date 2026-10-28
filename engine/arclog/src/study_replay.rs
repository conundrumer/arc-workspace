//! Exact historical mutation replay, always re-certified by the engine.
//! A runtime check must not substitute a fresh draw for a logged identity.
use super::*;
use crate::program::path::PathStep;

type Read<T>=Result<T,String>;
fn text(v:&Value)->Read<&str> {v.as_str().ok_or_else(||"identity expects a string".into())}
fn number(v:&Value)->Read<u32> {v.as_u64().and_then(|n|n.try_into().ok()).ok_or_else(||"identity expects a u32".into())}
fn array(v:&Value)->Read<&[Value]> {v.as_array().map(Vec::as_slice).ok_or_else(||"identity expects an array".into())}
fn path(v:&Value)->Read<NodePath> {Ok(NodePath(array(v)?.iter().map(|n|number(n).map(PathStep)).collect::<Read<_>>()?))}
fn name(v:&Value)->Read<DeclaredName> {if v.get("slot").is_some() {Ok(DeclaredName::Slot(number(&v["slot"])?))} else {Ok(DeclaredName::Written(text(&v["name"])?.into()))}}
fn column(v:&Value)->Read<ColumnName> {if v.get("slot").is_some() {Ok(ColumnName::Slot(number(&v["slot"])?))} else {Ok(ColumnName::Written(text(&v["name"])?.into()))}}
fn label(v:&Value)->Read<LabelUse> {
    for (key,kind) in [("fresh",0),("join",1),("key",2)] {if let Some(n)=v.get(key) {let id=LabelId(number(n)?);return Ok(match kind {0=>LabelUse::Fresh(id),1=>LabelUse::Join(id),_=>LabelUse::Key(id)});}}
    if v["zero"]==true {Ok(LabelUse::Zero)} else {Err("identity has no label use".into())}
}
fn site(v:&Value)->Read<Site> {
    let args=array(&v["args"])?.iter().map(|a| {
        if let Some(s)=a.get("site") {Ok(SiteArg::Field(site(s)?))}
        else if let Some(field)=a.get("field") {Ok(SiteArg::NamedLabel {name:column(field)?,label:label(&a["label"])?})}
        else {Ok(SiteArg::Label(label(a)?))}
    }).collect::<Read<_>>()?;
    Ok(Site {column:column(&v["column"])?,value:SiteValue {args}})
}
fn relation(v:&Value)->Read<RelationRef> {
    if let Some(f)=v.get("fact") {return Ok(RelationRef::Fact(match text(f)? {"Input"=>FactRelation::Input,"ExInput"=>FactRelation::ExInput,"ExOutput"=>FactRelation::ExOutput,_=>return Err("identity has an unknown fact".into())}));}
    if let Some(n)=v.get("lib") {return Ok(RelationRef::Lib(crate::registry::LibName(text(n)?.into())));}
    if let Some(n)=v.get("declared") {return Ok(RelationRef::Declared(RelationName(name(n)?)));}
    if let Some(n)=v.get("input_port") {return Ok(RelationRef::DefinedPort(PortName(text(n)?.into())));}
    let of=if let Some(n)=v["owner"].get("instance") {OutputOwner::Instance(InstanceName(name(n)?))} else {OutputOwner::RigidDet(RigidDetName(name(&v["owner"]["rigid"])?))};
    let steps=array(&v["path"])?.iter().map(|p| {
        if let Some(n)=p.get("port") {Ok(OutputStep::Port(PortName(text(n)?.into())))}
        else if let Some(n)=p.get("part") {Ok(OutputStep::Part(name(n)?))}
        else if p["pose"]==true {Ok(OutputStep::Pose)} else {Err("identity has an unknown output step".into())}
    }).collect::<Read<_>>()?;
    Ok(RelationRef::Output(OutputName {of,path:steps}))
}
fn constrained(v:&Value)->Read<ConstraintLabel> {Ok(ConstraintLabel {label:LabelId(number(&v["label"])?),fresh:v["fresh"].as_bool().ok_or("identity expects a fresh flag")?})}
fn conjunct(v:&Value)->Read<Conjunct> {
    match text(&v["node"])? {
        "atom"|"not_atom"=>{
            let atom=Node::new(Atom {relation:relation(&v["relation"])?,sites:array(&v["sites"])?.iter().map(site).collect::<Read<_>>()?});
            Ok(if v["node"]=="not_atom" {Conjunct::Not(Negated::Atom(atom))} else {Conjunct::Atom(atom)})
        }
        "comparison"=>{
            let op=match text(&v["op"])? {"Eq"=>ConstraintOp::Eq,"Ne"=>ConstraintOp::Ne,"Lt"=>ConstraintOp::Lt,"Le"=>ConstraintOp::Le,"Gt"=>ConstraintOp::Gt,"Ge"=>ConstraintOp::Ge,_=>return Err("identity has an unknown comparison".into())};
            let second=if v["second"]["zero"]==true {Operand::Zero} else {Operand::Label(constrained(&v["second"])?) };
            Ok(Conjunct::Constraint(Constraint {op,first:constrained(&v["first"])?,second}))
        }
        _=>Err("identity replacement is not a leaf atom".into()),
    }
}
impl StudyProgram {
    /// Re-certify the exact logged identity against this gold handle. This
    /// bypasses sampling, never binding/type/interface checks or AST audit.
    pub fn replay_spec(&self,identity:&Value,registry:&Registry,settings:&DecodeSettings)->Read<MutationSpec> {
        let body=path(&identity["body"])?;
        let point=self.mutation_points().into_iter().find(|p|p.body==body).ok_or("identity body is not a mutation point")?;
        if point.clause!=path(&identity["clause"])? {return Err("identity clause/body mismatch".into());}
        let mut edits=Vec::new();
        for e in array(&identity["edits"])? {
            let at=path(&e["at"])?;
            if !point.atoms.contains(&at) {return Err("identity edit is outside its mutation point".into());}
            let kind=match text(&e["kind"])? {"argument"=>"argument","relation"=>"relation","comparison"=>"comparison","delete"=>"delete",_=>return Err("identity has an unknown edit kind".into())};
            let replacement=if e["replacement"].is_null() {None} else {Some(conjunct(&e["replacement"])?)};
            if (kind=="delete")!=replacement.is_none() {return Err("identity deletion kind/replacement mismatch".into());}
            edits.push(AtomEdit {at,replacement,kind,choice_kind:kind});
        }
        if edits.is_empty() {return Err("identity has no edits".into());}
        edits.sort_by(|a,b|a.at.cmp(&b.at));
        let ast=edit::apply(self.program(),&edits)?;
        let certified=StudyProgram::from_program_cached(ast,edit::layout(self.layout(),&edits),registry,&mut CheckCache::default())?;
        certified.decode_stream(registry,settings)?;
        let source=&identity["source"];
        let spec=MutationSpec {source:Arc::clone(self.checked()),point,origin:Source {revision:text(&source["revision"])?.into(),task:text(&source["task"])?.into(),case:text(&source["case"])?.into()},edits,certified};
        if spec.identity()!=*identity {return Err("identity is not a canonical mutation identity".into());}
        let mutant=self.construct(&spec).map_err(str::to_owned)?;
        mutant.audit()?;
        Ok(spec)
    }
}
