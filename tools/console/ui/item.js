/* An item as the rail and the detail pane read it: its stage chain, the
   cache freshness of its phase-owning session, the chime when a cache is
   about to go cold, and the state names the console shares with the server. */
import { fmtDur } from "/ui/prose.js";

export const TTL_MIN = 60;
export const TTL_ALERT = 10;   // minutes left when a cache goes hot and rings
export const FINAL = "finalize";
export const STATES = ["needs-review","commented","running","queued","approved","committed"];
export const SETTLED = ["approved","committed"];   // nothing left for a finalize pass to do

export const stateRank = it => { const i=STATES.indexOf(it.state); return i<0?STATES.length:i; };
export const NO_ITEM = {feed:[], files:[]};   // stands in until /api/item lands

export const draftKey = id => "draft:"+id;

/* the item's stage chain: every per-session readout is keyed by stage name */
export const stagesOf = it => it.chain||[];
export const stageNames = it => stagesOf(it).map(x=>x.name);
export const stageOf = (it,s) => stagesOf(it).find(x=>x.name===s) || {name:s, backend:"claude", model:""};
export const modelOf = (it,s) => stageOf(it,s).model || "";
export const backendOf = (it,s) => stageOf(it,s).backend || "claude";
export const nextName = it => { const ns=stageNames(it), i=ns.indexOf(it.phase);
  return i>=0 && i+1<ns.length ? ns[i+1] : null; };
export const modelShort = (it,s) => { const m=modelOf(it,s);
  if(!m) return "?";
  return backendOf(it,s)==="codex" ? m.replace(/-codex$/,"") : m.replace(/^claude-/,"").split("-")[0]; };
export const stageLabel = (it,s) => s+" · "+(backendOf(it,s)==="codex"?"codex ":"")+modelShort(it,s);
/* interactive commands that reproduce the workers' prompt bytes (cache reuse),
   on the model the worker ran so the resumed session keeps its cache */
export const takeoverCmd = (it,s,cli) => backendOf(it,s)==="codex"
  ? "codex exec resume "+it.sessions[s]
  : "claude --resume "+it.sessions[s]
    +(modelOf(it,s)?" --model "+modelOf(it,s):"")
    +` --append-system-prompt-file ${it.append} --add-dir ${cli.addDir} --exclude-dynamic-system-prompt-sections`;
export const hasTab = (it,s) => !!(it.sessions[s]) || it.phase===s;

/* Minutes left on the session's cache. A session with no stamp holds no
   cache, so it has none left. */
const ttlLeft = it => {
  const la = it.lastActive && it.lastActive[it.phase];
  return la ? TTL_MIN - (Date.now()-la)/60000 : 0;
};

/* When a turn of the item last landed, over all its stages; an item with no
   landing yet has none. */
export const lastTurn = it =>
  Math.max(0, ...Object.values(it.lastActive||{}).map(v=>v||0));

/* cache freshness of the phase-owning session: minutes until its 1h
   prompt-cache TTL expires. The sort key carries the rail order: a phase with
   no session yet leads, then the live turns, then the warm ones by
   nearest expiry. A cold cache is past saving, so those sort by state
   instead and the rail groups them the way the counts row reads. */
export function cacheInfo(it){
  if(!it.sessions || !it.sessions[it.phase]) return {cls:"none", txt:"—", sort:-1};
  if(it.active) return {cls:"active", sort:5e8,
    txt: it.turnStarted ? fmtDur(Date.now()/1000-it.turnStarted) : "active"};
  const rem = ttlLeft(it);
  if(rem<=0) return {cls:"cold", txt:"cold", sort:1e9+stateRank(it)};
  const cls = rem<TTL_ALERT?"hot":rem<30?"warn":"ok";
  return {cls, txt:Math.ceil(rem)+"m", sort:rem};
}

/* A cache crossing TTL_ALERT rings once. An item is armed while its
   countdown sits above the threshold, so one first seen below it stays
   silent and a reload does not replay crossings already past. A finished
   turn moves lastActive forward, which arms the next cycle. */
const ttlArmed = new Map();   // item id -> the lastActive it was armed for
const TTL_QUIET = new Set(["approved","committed"]);   // settled, let them go cold

export function ttlWatch(items){
  for(const it of items){
    if(it.active || TTL_QUIET.has(it.state) ||
       !it.sessions || !it.sessions[it.phase]) continue;
    const la = it.lastActive && it.lastActive[it.phase];
    const rem = ttlLeft(it);
    if(rem>=TTL_ALERT) ttlArmed.set(it.id, la);
    else if(rem>0 && ttlArmed.get(it.id)===la){ ttlArmed.delete(it.id); ding(); }
  }
}

/* Two-tone chime. WebAudio opens suspended until the page has seen a
   gesture, so the first click or keypress in the console unlocks it. */
let actx = null;
function audio(){
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if(!actx && Ctx) actx = new Ctx();
  return actx;
}
export function ding(){
  const ac = audio();
  if(!ac || ac.state!=="running") return;
  const t0 = ac.currentTime;
  [880, 1320].forEach((hz,i)=>{
    const at = t0 + i*0.14;
    const osc = ac.createOscillator(), gain = ac.createGain();
    osc.type="sine"; osc.frequency.value=hz;
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(0.2, at+0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, at+0.3);
    osc.connect(gain).connect(ac.destination);
    osc.start(at); osc.stop(at+0.32);
  });
}
for(const ev of ["pointerdown","keydown"])
  addEventListener(ev, ()=>{ const ac=audio(); if(ac) ac.resume(); }, {once:true});
