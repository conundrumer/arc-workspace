/* The shell: the frame every lens shares. It holds the active lens, the
   selection, the top bar and its panels, the toast, and the keys; a lens
   fills the rail, the middle column, and the code pane through its hook.

   A lens is an object {id, use(ctx)}. use() is a hook the host calls with
   {snap, selId, setSelId, pins, cli} and returns:
     order      the ids j/k step through, in rail order
     pick(id)   the id to hold selected: id itself while it exists, else a fallback
     settle(id) loads what a fallback selection shows
     select(id) the user's pick: selects and loads
     detailId   the id whose task the task strip shows
     sections   the rail's sections, see rail.js
     head, body the middle column; a null body shows the placeholder
     composer   the composer's props
     code       the code pane's props, or null
     keys       {key, label, run, show?, inBox?} — inBox keys fire inside a field
   A lens may also carry Controls, a component the top bar renders, and
   Panels, one rendered with the side panels; each gets the snapshot. */
import { html, render, useState, useEffect, useRef, useCallback } from "/vendor/htm-preact-standalone.module.js";
import { onTick } from "/ui/clock.js";
import { FINAL, ttlWatch } from "/ui/item.js";
import { finalize } from "/ui/lens/finalize.js";
import { wave } from "/ui/lens/wave.js";
import { CitePop, useCitations } from "/ui/panels/cite.js";
import { CodePane } from "/ui/panels/codepane.js";
import { CommitPanel } from "/ui/panels/commit.js";
import { Composer } from "/ui/panels/composer.js";
import { NightPanel } from "/ui/panels/night.js";
import { TaskStrip } from "/ui/panels/taskstrip.js";
import { Topbar } from "/ui/panels/topbar.js";
import { Rail } from "/ui/rail.js";
import { snap as snapNow, tasks, notify, useServer, post, ensureTask, startPoll } from "/ui/server.js";
import { bindToast, toast } from "/ui/toast.js";

const LENSES = {wave, [FINAL]: finalize};
const NO_CODE = {jumpKey:"", fname:"—", lines:"", buttons:null, pane:""};

/* the keys every lens has, around the lens's own */
const KEYS_LEAD = [
  {key:"j", show:"j/k", label:"move", run:(e,st)=>{
    const {order,selId,L}=st, pos=order.indexOf(selId);
    if(order.length) L.select(order[Math.min(pos+1,order.length-1)]); }},
  {key:"k", run:(e,st)=>{
    const {order,selId,L}=st, pos=order.indexOf(selId);
    if(order.length) L.select(order[Math.max(pos-1,0)]); }},
];
const KEYS_TAIL = [
  {key:"t", label:"task", run:(e,st)=>st.toggleTask()},
  {key:"v", label:"lens", run:(e,st)=>st.setView(st.view===FINAL?"wave":FINAL)},
  {key:"Escape", show:"esc", label:"blur"},
];

function LensHost({lens, snap, selId, setSelId, pins, cli, view, setView, taskOpen, setTaskOpen}){
  const L=lens.use({snap, selId, setSelId, pins, cli});
  const live=useRef({});
  const toggleTask=useCallback(()=>{
    const id=live.current.L.detailId;
    if(!id) return;
    setTaskOpen(o=>({...o, [id]: !(o[id]!==false)}));
  },[]);
  live.current={L, order:L.order, selId, view, setView, toggleTask};

  /* ---- selection stays on something that exists ---- */
  useEffect(()=>{
    const id=L.pick(selId);
    if(id!==selId){
      setSelId(id);
      if(id) L.settle(id);
    }
  });
  useEffect(()=>{ if(L.detailId) ensureTask(L.detailId); },[L.detailId]);

  /* ---- keys ---- */
  useEffect(()=>{
    const h=e=>{
      if(e.metaKey||e.ctrlKey||e.altKey) return;
      const st=live.current;
      /* type-ahead in a select, and every key a field of its own reads */
      const inBox = ["INPUT","SELECT","TEXTAREA"].includes(e.target.tagName);
      if(e.key==="Escape"){ if(inBox) e.target.blur(); return; }
      if(inBox){
        const k=st.L.keys.find(x=>x.inBox && x.key===e.key);
        if(k) k.run(e, st);
        return;
      }
      const k=[...KEYS_LEAD, ...st.L.keys, ...KEYS_TAIL].find(x=>x.key===e.key && x.run && !x.inBox);
      if(k) k.run(e, st);
    };
    document.addEventListener("keydown", h);
    return ()=>document.removeEventListener("keydown", h);
  },[]);

  const body = L.body || html`<div id="judge-scroll" key="none">
    <p class="placeholder">${snap.items.length?"select an item":"no items — start a wave"}</p>
  </div>`;
  return html`
    <div id="main">
      <${Rail} sections=${L.sections}/>
      <div id="judge">
        <div id="judge-head">${L.head}</div>
        ${body}
        <${Composer} ...${L.composer}/>
      </div>
      <div id="codecol">
        <${TaskStrip} id=${L.detailId} task=${L.detailId?tasks[L.detailId]:null}
          open=${L.detailId ? taskOpen[L.detailId]!==false : true} onToggle=${toggleTask}/>
        <${CodePane} ...${L.code||NO_CODE}/>
      </div>
    </div>
    <div id="keysbar">
      ${[...KEYS_LEAD, ...L.keys, ...KEYS_TAIL].filter(k=>k.label).map(k=>html`
        <span key=${k.label}><b>${k.show||k.key}</b> ${k.label}</span>`)}
    </div>`;
}

function App(){
  const snap=useServer();
  const [selId,setSelId]=useState(null);
  const [view,setViewState]=useState(()=>localStorage.getItem("view")===FINAL?FINAL:"wave");
  const [toastState,setToastState]=useState({msg:"", show:false});
  const [sessPin,setSessPin]=useState({});    // id -> {phase, tab} the user pinned
  const [tabSel,setTabSel]=useState({});      // id -> path of the active code tab
  const [taskOpen,setTaskOpen]=useState({});  // id -> bool (default open)
  const [nightOpen,setNightOpen]=useState(()=>!!localStorage.getItem("nightOpen"));
  const [waveK,setWaveK]=useState("10");
  const [waveOrder,setWaveOrder]=useState("name");
  const [commitOpen,setCommitOpen]=useState(()=>!!localStorage.getItem("commitOpen"));
  const [waveBusy,setWaveBusy]=useState(false);
  const [cite,closeCite]=useCitations();

  bindToast(setToastState);
  const live=useRef({});        // what the async handlers read
  const lens=LENSES[view];
  const {items, cli, night, committer, auto, usage, progress, wave:waveN} = snap;
  const pins={sessPin, setSessPin, tabSel, setTabSel};

  const setView=useCallback(v=>{
    setViewState(cur=>{
      if(cur===v) return cur;
      localStorage.setItem("view", v);
      return v;
    });
  },[]);

  /* ---- actions ---- */
  const commitApproved=useCallback(async()=>{
    const r=await post("/api/commit");
    if(r.ok) toast('git commit -m "'+r.msg+'"');
  },[]);
  const startWave=useCallback(async()=>{
    const st=live.current;
    if(st.waveBusy) return;
    setWaveBusy(true);
    try {
      const k=parseInt(st.waveK,10)||6;
      const r=await post("/api/wave",{k, order:st.waveOrder});
      if(r.ok) toast("wave started · "+r.ids.join(", "));
    } finally {
      setTimeout(()=>setWaveBusy(false), 5000);   // matches WAVE_DEBOUNCE
    }
  },[]);
  /* the settings are the server's; a control mirrors one, and the next poll
     confirms an edit */
  const onAuto=useCallback(async(name, on)=>{
    const r=await post("/api/auto",{[name]:on});
    if(r.ok) toast("auto "+name+(on?" on":" off"));
  },[]);
  const postNight=useCallback(async(body, note)=>{
    const r=await post("/api/night", body);
    if(r.ok && note) toast(note);
  },[]);
  const onNightToggle=useCallback(on=>{
    if(on){
      const n=live.current.night||{};
      const queueText="admits tasks from the queue: up to "+(n.target??6)
        +" items in flight, create → refine";
      const finText="starts finalize passes over the unfinalized solvers, in triage order: up to "
        +(n.finalize_target??3)+" in flight";
      const ok=confirm("Autopilot "+(n.source==="unfinalized" ? finText
        : n.source==="both" ? queueText+", and "+finText
        : queueText+((live.current.auto||{}).finalize?" → finalize":""))
        +", within ~30s of the pacer opening. Start?");
      if(!ok){ notify(); return; }   // the checkbox mirrors the server, so redraw it
    }
    postNight({on}, on?"autopilot on":"autopilot off");
  },[postNight]);

  /* ---- what the async handlers read ---- */
  live.current = {auto, night, waveK, waveOrder, waveBusy};

  /* ---- timers ---- */
  useEffect(()=>onTick(()=>ttlWatch(snapNow().items)),[]);

  /* ---- view side effects ---- */
  useEffect(()=>{
    document.body.classList.toggle("view-final", view===FINAL);
  },[view]);

  return html`
    <${Topbar} view=${view} setView=${setView} wave=${waveN} items=${items}
      progress=${progress} usage=${usage} night=${night} nightOpen=${nightOpen}
      committer=${committer} commitOpen=${commitOpen} onCommit=${commitApproved}
      toggleNight=${()=>setNightOpen(o=>{ localStorage.setItem("nightOpen", o?"":"1"); return !o; })}
      toggleCommit=${()=>setCommitOpen(o=>{ localStorage.setItem("commitOpen", o?"":"1"); return !o; })}
      auto=${auto} onAuto=${onAuto}
      waveCtl=${{k:waveK, setK:setWaveK, order:waveOrder, setOrder:setWaveOrder,
                 busy:waveBusy, start:startWave}}
      extra=${lens.Controls && html`<${lens.Controls} snap=${snap}/>`}/>
    <${NightPanel} night=${night} open=${nightOpen} onToggle=${onNightToggle}
      onCatchup=${v=>postNight({catchup:v})}
      onSource=${v=>postNight({source:v}, "source · "+v)}
      onDial=${(key,v)=>postNight({[key]:parseInt(v,10)})}/>
    <${CommitPanel} committer=${committer} open=${commitOpen}/>
    ${lens.Panels && html`<${lens.Panels} snap=${snap}/>`}
    <${LensHost} key=${view} lens=${lens} snap=${snap}
      selId=${selId} setSelId=${setSelId} pins=${pins} cli=${cli}
      view=${view} setView=${setView} taskOpen=${taskOpen} setTaskOpen=${setTaskOpen}/>
    ${cite && html`<${CitePop} cite=${cite} task=${tasks[cite.tid]}
      onClose=${closeCite}/>`}
    <div id="toast" role="status" class=${toastState.show?"show":""}>${toastState.msg}</div>`;
}

startPoll();
render(html`<${App}/>`, document.getElementById("app"));
