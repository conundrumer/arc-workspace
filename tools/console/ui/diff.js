/* Code pane markup: a file with this turn's edits marked, line by line
   against the turn-start snapshot, with word-level marks in replaced
   hunks. */
import { esc } from "/ui/prose.js";

/* ---------- code pane markup ----------
   The file with this turn's edits marked, removed lines included. Every line
   renders as an .L block whose CSS counter numbers it; removed lines are
   skipped so the gutter tracks the file on disk. Line diff vs the turn-start
   snapshot; replaced hunks get word-level marks. */
const cmline = l => esc(l).replace(/(\/\/.*)/,'<span class="cm">$1</span>');
export const cmify = s => splitLines(s).map(l=>'<span class="L">'+(cmline(l)||" ")+"</span>").join("");
function splitLines(v){ const ls=v.split("\n"); if(ls[ls.length-1]==="") ls.pop(); return ls; }
function markBlock(v, cls){
  return splitLines(v).map(l=>`<span class="L ${cls}">`+(esc(l)||" ")+"</span>").join("");
}
/* One side of a replaced hunk: its own lines, with the words that differ from
   the other side marked. `side` picks which of the two the caller wants. */
function wordSide(rem, add, side){
  const [cls, markCls] = side==="removed" ? ["del","delw"] : ["add","addw"];
  const lines=[[]];
  for(const p of Diff.diffWordsWithSpace(rem, add)){
    if(p.removed && side!=="removed") continue;
    if(p.added && side!=="added") continue;
    const marked = side==="removed" ? !!p.removed : !!p.added;
    p.value.split("\n").forEach((s,si)=>{
      if(si>0) lines.push([]);
      if(s) lines[lines.length-1].push({s, marked});
    });
  }
  if(lines.length && !lines[lines.length-1].length) lines.pop();
  return lines.map(segs=>{
    // whitespace between two changed runs joins them, so a highlight covering
    // several words reads as one and does not break at the spaces
    for(let i=1;i<segs.length-1;i++)
      if(!segs[i].marked && !segs[i].s.trim() && segs[i-1].marked && segs[i+1].marked)
        segs[i].marked=true;
    let body="";
    for(let i=0;i<segs.length;){
      let j=i;
      while(j<segs.length && segs[j].marked===segs[i].marked) j++;
      const text=esc(segs.slice(i,j).map(g=>g.s).join(""));
      body += segs[i].marked ? `<mark class="${markCls}">`+text+"</mark>" : text;
      i=j;
    }
    return `<span class="L ${cls}">`+(body||" ")+"</span>";
  }).join("");
}
export function diffHtml(before, after){
  const parts=Diff.diffLines(before, after);
  let html="", added=0, removed=0;
  for(let k=0;k<parts.length;k++){
    const p=parts[k];
    if(p.removed){
      const nxt=parts[k+1];
      removed+=splitLines(p.value).length;
      if(nxt && nxt.added){
        html+=wordSide(p.value, nxt.value, "removed")+wordSide(p.value, nxt.value, "added");
        added+=splitLines(nxt.value).length; k++;
      } else {
        html+=markBlock(p.value,"del");
      }
    } else if(p.added){
      html+=markBlock(p.value,"add"); added+=splitLines(p.value).length;
    } else {
      html+=cmify(p.value);
    }
  }
  return {html, added, removed};
}
