/* The server as the page sees it: the long-polled snapshot, the per-item
   fetches and the caches they fill, and the posts. A component reads the
   snapshot through useServer() and redraws when a poll or a fetch lands. */
import { useState, useEffect } from "/vendor/htm-preact-standalone.module.js";
import { toast } from "/ui/toast.js";

let SNAP = {seq:0, wave:0, items:[], usage:[], progress:null,
            cli:{}, night:{}, committer:{}, pipeline:{}, models:[], auto:{}};
export const snap = () => SNAP;

export const tasks = {};      // id -> task json | "pending" | "missing"
export const itemData = {};   // id -> {feed, files, ver}
export const peeks = {};      // id -> peek json

const subs = new Set();
let ver = 0;
/* a redraw for every subscriber: a fetch landed, or a mirror needs to snap back */
export function notify(){ ver++; for(const f of subs) f(ver); }
export function useServer(){
  const [,set]=useState(ver);
  useEffect(()=>{ subs.add(set); return ()=>subs.delete(set); },[]);
  return SNAP;
}

const sleep = ms => new Promise(r=>setTimeout(r,ms));

export async function post(route, body){
  try {
    const r = await fetch(route,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})});
    const j = await r.json();
    if(j.error) toast(j.error);
    return j;
  } catch(e){ toast("console server unreachable"); return {error:String(e)}; }
}

/* ---- fetches ---- */
export function ensureTask(id){
  if(!id || tasks[id]) return;
  tasks[id]="pending";
  fetch("/api/task/"+id).then(r=>r.ok?r.json():"missing").then(t=>{
    tasks[id]=t; notify();
  }).catch(()=>{ tasks[id]="missing"; });
}
export function ensureItem(id, force){
  const cached=itemData[id], it=SNAP.items.find(x=>x.id===id);
  if(cached && it && cached.ver===it.ver && !force) return;
  fetch("/api/item/"+id).then(r=>r.json()).then(d=>{
    itemData[id]=d; notify();
  }).catch(()=>{});
}
export function ensurePeek(id){
  fetch("/api/peek/"+id).then(r=>r.ok?r.json():null).then(d=>{
    if(d){ peeks[id]=d; notify(); }
  }).catch(()=>{});
}

/* ---- long poll ---- */
/* runs for the life of the page; the snapshot's seq moves only when the
   server's state did, so an effect on it sees each change once */
export function startPoll(){
  let seq=0, committerWas=false;
  (async ()=>{
    for(;;){
      try {
        const r=await fetch(`/api/state?since=${seq}&wait=25`);
        const d=await r.json();
        seq=d.seq;
        SNAP={seq:d.seq, wave:d.wave, items:d.items, usage:d.usage||[],
              progress: d.total ? {solved:d.solved, total:d.total} : null,
              cli:d.cli||{}, night:d.night||{}, committer:d.committer||{},
              pipeline:d.pipeline||{}, models:d.models||[], auto:d.auto||{}};
        notify();
        const cm=d.committer||{};
        if(committerWas && !cm.running && cm.note) toast(cm.note);
        committerWas=!!cm.running;
      } catch(e){
        await sleep(3000);
      }
    }
  })();
}
