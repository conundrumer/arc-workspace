/* The page's second hand. A component that shows a countdown or a running
   timer subscribes with useClock() and redraws each second on its own; a
   value that depends on the time but seldom changes is held with
   useClocked(), which redraws its owner only when the value moves. */
import { useState, useEffect, useRef, useMemo } from "/vendor/htm-preact-standalone.module.js";

const subs = new Set();
let tick = 0;
setInterval(()=>{ tick++; for(const f of subs) f(tick); }, 1000);

export function onTick(f){ subs.add(f); return ()=>subs.delete(f); }

export function useClock(){
  const [t,setT]=useState(tick);
  useEffect(()=>onTick(setT),[]);
  return t;
}

const sameList = (a,b) => a===b || (Array.isArray(a) && Array.isArray(b)
  && a.length===b.length && a.every((x,i)=>x===b[i]));

/* compute() runs when deps move and on each tick; `same` says when two
   results are one value, and only a different one redraws */
export function useClocked(compute, deps, same=sameList){
  const [,redraw]=useState(0);
  const cur=useRef();
  useMemo(()=>{ cur.current=compute(); }, deps);
  useEffect(()=>onTick(()=>{
    const n=compute();
    if(!same(cur.current,n)){ cur.current=n; redraw(x=>x+1); }
  }), deps);
  return cur.current;
}
