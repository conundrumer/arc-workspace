/* The toast line at the foot of the page, and the clipboard copy that
   reports through it. The page binds the setter that shows it. */

let toastSet = () => {};
let toastTimer = null;
export function bindToast(set){ toastSet = set; }
export function toast(msg){
  toastSet({msg, show:true});
  clearTimeout(toastTimer);
  toastTimer = setTimeout(()=>toastSet(t=>({msg:t.msg, show:false})), 2600);
}
export function copy(s,label){ navigator.clipboard && navigator.clipboard.writeText(s).then(()=>toast("copied · "+label),()=>toast(s)); }
