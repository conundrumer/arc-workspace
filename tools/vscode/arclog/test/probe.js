// Prints the scopes the grammars give each token of a few lines.
const fs=require('fs'),vt=require('vscode-textmate'),onig=require('vscode-oniguruma');
const EXT='/Users/davidlu/code/arc-workspace/work/vscode-arclog/syntaxes/';
(async()=>{await onig.loadWASM(fs.readFileSync(require.resolve('vscode-oniguruma/release/onig.wasm')).buffer);
const reg=new vt.Registry({onigLib:Promise.resolve({createOnigScanner:p=>new onig.OnigScanner(p),createOnigString:s=>new onig.OnigString(s)}),
loadGrammar:async s=>({'source.arclog':'arclog','source.arcscene':'arcscene'}[s]?vt.parseRawGrammar(fs.readFileSync(EXT+{'source.arclog':'arclog','source.arcscene':'arcscene'}[s]+'.tmLanguage.json','utf8'),'x.json'):null)});
const g=await reg.loadGrammar(process.argv[2]);let st=vt.INITIAL;
for(const s of process.argv.slice(3)){const r=g.tokenizeLine(s,st);st=r.ruleStack;
for(const t of r.tokens){const x=s.slice(t.startIndex,t.endIndex);if(x.trim()&&!/^[()]+$/.test(x))console.log(JSON.stringify(x),t.scopes.slice(1).join(' '));}}})();
