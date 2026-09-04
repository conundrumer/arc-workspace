/* Prose rendering: markdown to HTML, ARC cell runs painted in the palette
   colors, grid citations marked as chips, and the escapes and time
   formats every pane shares. */

export const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
export const pad2 = n => String(n).padStart(2,"0");
export const hhmm = e => { const d=new Date(e*1000);
  return String(d.getHours()).padStart(2,"0")+":"+String(d.getMinutes()).padStart(2,"0"); };
export const fmtDur = s => { s=Math.max(0,Math.floor(s)); const h=Math.floor(s/3600), m=Math.floor((s%3600)/60);
  return h ? h+"h "+m+"m" : m ? m+"m "+String(s%60).padStart(2,"0")+"s" : s+"s"; };

/* ARC grid and color rendering. A cell run is ≥3 single digit-or-dot cells
   separated by 1-2 spaces, or ≥3 contiguous digits; a fenced block with two
   such lines is a grid, and every digit in its runs gets its palette color.
   An inline code span takes the spaced form only, so a bare number stays
   plain; a span that is exactly one digit is a color swatch, as is the digit
   of "color N" in prose. */
const RUN_SP = /[0-9.](?: {1,2}[0-9.]){2,}/g;
/* the contiguous form stands alone, so a task id or path digit is no cell */
const RUN_ANY = /(?:[0-9.](?: {1,2}[0-9.]){2,})|(?<![\w./])[0-9]{3,}(?![\w./])/g;
const COLOR_RE = /\b(colou?r )([0-9])\b/g;
/* a grid citation: pair, side, then comma-separated places — points and
   row/col ranges. Binds only when the places directly follow the side token. */
const PLACE = String.raw`\(\s*\d+\s*,\s*\d+\s*\)|(?:rows?|cols?|columns?) ?\d+(?: ?[–-] ?\d+)?`;
const CITE = new RegExp(String.raw`\b(train|test) ?(\d) (input|output) ((?:${PLACE})(?:,\s*(?:${PLACE}))*)`, "g");
const hasDigit = s => /[0-9]/.test(s);
function paintRuns(text, re){
  re.lastIndex = 0;
  let out = "", i = 0;
  for(const m of text.matchAll(re)){
    if(!hasDigit(m[0])) continue;
    out += esc(text.slice(i, m.index))
         + m[0].replace(/./g, c => c>="0"&&c<="9" ? `<span class="cw cw${c}">${c}</span>` : esc(c));
    i = m.index + m[0].length;
  }
  return i ? out + esc(text.slice(i)) : null;
}
function colorized(html){
  const t = document.createElement("template");
  t.innerHTML = html;
  for(const code of t.content.querySelectorAll("code")){
    const text = code.textContent;
    if(code.closest("pre")){
      const rows = text.split("\n").filter(l => (l.match(RUN_ANY)||[]).some(hasDigit)).length;
      if(rows < 2) continue;
      const painted = paintRuns(text, RUN_ANY);
      if(painted !== null) code.innerHTML = painted;
    } else if(/^[0-9]$/.test(text)){
      code.classList.add("cw", "cw"+text);
    } else {
      const painted = paintRuns(text, RUN_SP);
      if(painted !== null) code.innerHTML = painted;
    }
  }
  const tw = document.createTreeWalker(t.content, NodeFilter.SHOW_TEXT);
  const hits = [];
  for(let n; (n = tw.nextNode()); ){
    if(!n.parentElement || n.parentElement.closest("code,pre")) continue;
    const rep = proseHTML(n.nodeValue);
    if(rep !== null) hits.push([n, rep]);
  }
  for(const [n, rep] of hits){
    const frag = document.createElement("template");
    frag.innerHTML = rep;
    n.replaceWith(frag.content);
  }
  return t.innerHTML;
}
function swatched(text){
  COLOR_RE.lastIndex = 0;
  if(!COLOR_RE.test(text)) return null;
  return esc(text).replace(COLOR_RE, (_, w, d) => `${w}<span class="cw cw${d}">${d}</span>`);
}
/* citation chips and color swatches in one prose text node; null when neither */
export function proseHTML(text){
  CITE.lastIndex = 0;
  let out = "", i = 0;
  for(const m of text.matchAll(CITE)){
    const pre = text.slice(i, m.index);
    out += swatched(pre) ?? esc(pre);
    out += `<span class="cite" data-pair="${m[1]+m[2]}" data-side="${m[3]}"`
         + ` data-places="${esc(m[4])}">${esc(m[0])}</span>`;
    i = m.index + m[0].length;
  }
  const tail = text.slice(i);
  const sw = swatched(tail);
  return i === 0 ? sw : out + (sw ?? esc(tail));
}

/* markdown is re-rendered on every tick otherwise; the text is the whole key */
const mdCache = new Map();
const mdOne = (typeof marked!=="undefined" && typeof DOMPurify!=="undefined")
  ? (t => colorized(DOMPurify.sanitize(marked.parse(t, {breaks:true}))))
  : (t => "<p>"+esc(t).replace(/\n/g,"<br>")+"</p>");
export function md(text){
  let out = mdCache.get(text);
  if(out===undefined){
    out = mdOne(text);
    if(mdCache.size>600) mdCache.clear();
    mdCache.set(text, out);
  }
  return out;
}
