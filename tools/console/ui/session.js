/* The selected live item's session: the tab in view, its feed, the comment
   draft, the turn actions, the keys that drive them, and the code pane on
   the file the turn touched. Both lenses show one through useSession(). */
import { html, useState, useEffect, useRef, useMemo, useCallback } from "/vendor/htm-preact-standalone.module.js";
import { cmify, diffHtml } from "/ui/diff.js";
import { NO_ITEM, draftKey, stageNames, nextName, takeoverCmd, hasTab } from "/ui/item.js";
import { DetailHead } from "/ui/panels/detail.js";
import { Feed } from "/ui/panels/feed.js";
import { itemData, post, ensureItem, useServer } from "/ui/server.js";
import { toast, copy } from "/ui/toast.js";

/* pins: the per-item choices the page keeps across lenses — the session
   tab pinned on an item, and the code tab in view.
   reviewOrder: the ids `n` steps through. afterRule: runs after a dismiss. */
export function useSession(selItem, {cli, reviewOrder, select, pins, afterRule}){
  const snap=useServer();
  const {sessPin, setSessPin, tabSel, setTabSel} = pins;
  const [draft,setDraft]=useState("");
  const seenN=useRef({});       // id|sess -> feed length when that tab was last shown
  const draftFor=useRef(null);  // id whose draft the composer holds
  const cbox=useRef(null);
  const live=useRef({});        // what the async handlers read

  /* ---- the session tab in view: the user's pin while it holds, else the stage ---- */
  const tabOf=useCallback(it=>{
    const pin=sessPin[it.id];
    const t = pin && pin.phase===it.phase ? pin.tab : null;
    return t && (it.sessions[t]||it.phase===t) ? t : it.phase;
  },[sessPin]);
  const pinTab=useCallback((it,s)=>setSessPin(p=>({...p, [it.id]:{phase:it.phase, tab:s}})),[]);

  const tab = selItem ? tabOf(selItem) : null;
  const cache = (selItem && itemData[selItem.id]) || NO_ITEM;
  const feedFor = s => (cache.feed||[]).filter(m=>(m.sess||"refine")===s);
  /* the entries hold their identity between fetches, so the second-by-second
     redraw for the countdowns leaves the feed alone */
  const entries = useMemo(()=>selItem?feedFor(tab):[], [cache, tab, selItem]);
  const tabBadges = {};
  if(selItem) for(const n of stageNames(selItem))
    tabBadges[n] = n!==tab && hasTab(selItem,n)
      && feedFor(n).length>(seenN.current[selItem.id+"|"+n]||0);
  useEffect(()=>{
    if(selItem) seenN.current[selItem.id+"|"+tab]=entries.length;
  });

  /* the task ids the prose of the tab in view names, besides the item's own;
     tool lines and events are left out, so a path or a hash in a command is
     no mention */
  const mentions = useMemo(()=>{
    const seen=new Set();
    for(const m of entries){
      if(m.kind==="tool" || m.kind==="event") continue;
      for(const w of (m.text||"").match(/\b[0-9a-f]{8}\b/g)||[]) seen.add(w);
    }
    if(selItem) seen.delete(selItem.id);
    return [...seen];
  },[entries, selItem && selItem.id]);

  const nxt = selItem ? nextName(selItem) : null;
  const canAdvance = !!(selItem && nxt && !selItem.active && selItem.hasReport
    && (selItem.state==="needs-review"||selItem.state==="approved"));
  const canResume = !!(selItem && selItem.cutPhase === tab && !selItem.active);
  const canSend = !!(selItem && selItem.sessions[tab]
    && !selItem.handoffPending && selItem.state!=="committed");

  /* ---- actions ---- */
  const nextReview=useCallback(()=>{
    const st=live.current;
    const revs=st.reviewOrder.filter(id=>{
      const it=st.items.find(x=>x.id===id);
      return it && it.state==="needs-review" && id!==st.selId; });
    if(revs.length) select(revs[0]); else toast("review queue empty");
  },[select]);
  const approve=useCallback(async()=>{
    const it=live.current.selItem;
    if(!it||it.state!=="needs-review"){ toast("nothing to approve"); return; }
    const r=await post("/api/approve",{id:it.id});
    if(r.ok) toast(it.id+" approved");
  },[]);
  const unapprove=useCallback(async()=>{
    const it=live.current.selItem;
    if(!it||it.state!=="approved"){ toast("not approved"); return; }
    const r=await post("/api/unapprove",{id:it.id});
    if(r.ok) toast(it.id+" back to review");
  },[]);
  const sendComment=useCallback(async()=>{
    const st=live.current, it=st.selItem, text=(st.draft||"").trim();
    if(!it||!text) return;
    if(!st.canSend){
      toast(it.handoffPending ? "handoff in flight — draft kept"
        : "no session yet — draft kept");
      return;
    }
    const low=text.toLowerCase();
    if(low==="commit"){ toast("commit is a console action"); return; }
    if(low==="next"){ toast("no next in batch mode"); return; }
    const r=await post("/api/comment",{id:it.id, text, sess:st.tab});
    if(r.ok){
      setDraft(""); localStorage.removeItem(draftKey(it.id));
      if(cbox.current) cbox.current.blur();
      toast((it.busy||{})[st.tab] ? "sent into the running turn" : "sent");
    }
  },[]);
  const dismiss=useCallback(async id=>{
    if(!confirm("Dismiss "+id+"? A ledger line records that it needs no finalize pass.")) return;
    await post("/api/dismiss",{id});
    if(afterRule) afterRule();
  },[afterRule]);

  /* ---- what the async handlers read ---- */
  live.current = {items:snap.items, selId:selItem?selItem.id:null, selItem, tab, draft, canSend, reviewOrder};

  /* ---- a server change: the selected item's turn may have landed ---- */
  useEffect(()=>{
    if(!snap.seq || !selItem) return;
    const have=itemData[selItem.id];
    if(!have || have.ver!==selItem.ver) ensureItem(selItem.id, true);
  },[snap.seq]);

  /* ---- per-item comment drafts ---- */
  useEffect(()=>{
    const id = selItem ? selItem.id : null;
    if(draftFor.current===id) return;
    draftFor.current=id;
    setDraft(id ? (localStorage.getItem(draftKey(id))||"") : "");
  },[selItem]);
  const onDraft=useCallback(v=>{
    setDraft(v);
    const id=draftFor.current;
    if(!id) return;
    if(v) localStorage.setItem(draftKey(id), v);
    else localStorage.removeItem(draftKey(id));
  },[]);

  /* ---- keys ---- */
  const keys=[
    {key:"n", label:"next review", run:nextReview},
    {key:"a", label:"approve", run:approve},
    {key:"u", label:"unapprove", run:unapprove},
    {key:"c", label:"comment", run:e=>{
      if(cbox.current && !cbox.current.disabled){ e.preventDefault(); cbox.current.focus(); } }},
    {key:"Enter", label:"send", show:"⏎", inBox:true, run:e=>{
      if(e.target===cbox.current && !e.shiftKey){ e.preventDefault(); sendComment(); } }},
    {key:null, label:"newline", show:"⇧⏎"},
    {key:"s", label:"session", run:()=>{
      const it=live.current.selItem;
      if(it){ const ns=stageNames(it).filter(n=>hasTab(it,n));
        if(ns.length>1) pinTab(it, ns[(ns.indexOf(live.current.tab)+1)%ns.length]); } }},
    {key:"o", label:"copy resume", run:()=>{
      const it=live.current.selItem;
      if(it){ const s=live.current.tab;
        if(it.sessions[s] && !(it.workerLive||{})[s]) copy(takeoverCmd(it,s,cli),"takeover "+it.id); } }},
  ];

  /* ---- code pane ---- */
  const files = cache.files || [];
  const f = files.find(x=>x.path===(selItem?tabSel[selItem.id]:null)) || files[0]
    || {path:"", snap:"", code:""};
  const codeBuilt = useMemo(()=>{
    if(!f.code) return {html:"", added:0, removed:0};
    if(f.snap && f.snap!==f.code && window.Diff) return diffHtml(f.snap, f.code);
    return {html:cmify(f.code), added:0, removed:0};
  },[f.path, f.snap, f.code]);

  let code=null, head=null, body=null, hint="";
  if(selItem){
    const turn=[codeBuilt.added?"+"+codeBuilt.added:"", codeBuilt.removed?"−"+codeBuilt.removed:""]
      .filter(Boolean).join(" ");
    const lines = f.code ? f.code.split("\n").length+" lines"+(turn?" · "+turn+" this turn":"") : "";
    const pane = f.code ? codeBuilt.html
      : '<span class="cm">// '+(selItem.state==="queued"?"not started":"no file yet")+"</span>";
    const fname = files.length>1
      ? files.map(x=>html`<span key=${x.path} class=${"ftab"+(x.path===f.path?" on":"")}
          onClick=${()=>setTabSel(t=>({...t, [selItem.id]:x.path}))}>${x.path.split("/").pop()}</span>`)
      : (f.code ? f.path : "—");
    const solver=files[0]||{};
    const canRevert = f.path===solver.path && solver.code && solver.snap
      && solver.snap!==solver.code && !selItem.active;
    const buttons = canRevert ? html`<button class="copybtn"
      onClick=${()=>post("/api/revert",{id:selItem.id})}>revert edits</button>` : null;
    code = {jumpKey:selItem.id+"|"+f.path, fname, lines, buttons, pane};

    head=html`<${DetailHead} it=${selItem} cli=${cli} tab=${tab} badges=${tabBadges}
      canAdvance=${canAdvance} canResume=${canResume} nxt=${nxt}
      onTab=${s=>pinTab(selItem,s)}
      onDismiss=${dismiss}/>`;
    body=html`<${Feed} key="feed" it=${selItem} entries=${entries}
      feedKey=${selItem.id+"|"+tab}
      showRun=${(selItem.busy||{})[tab] || (selItem.active && !selItem.turnPhase)}/>`;

    hint = selItem.state==="needs-review" && selItem.dirty ? "cleanup pending" : "";
    if(nxt && selItem.state==="needs-review" && selItem.sessions[selItem.phase])
      hint = (selItem.hasReport ? `report ready, advance to ${nxt}`
                                : "`handoff` when ready")+(hint?" · "+hint:"");
  }
  const composer = {boxRef:cbox, enabled:!!selItem, canSend,
    placeholder: selItem ? (canSend ? ((selItem.busy||{})[tab] ? "sends into the running turn" : "")
                            : selItem.handoffPending ? "handoff in flight — draft freely" : "no session yet") : "",
    hint, value:selItem?draft:"", onInput:onDraft, onSend:sendComment};

  return {tab, head, body, composer, code, keys, dismiss, mentions};
}
