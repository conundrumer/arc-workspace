// Tokenizes the arcscene files and a sample of the generated arclog files
// with the extension's grammars, and reports keyword tokens left unscoped and
// scene-only constructs whose scope differs from the expected one.
const fs = require('fs');
const path = require('path');
const vt = require('vscode-textmate');
const onig = require('vscode-oniguruma');

const EXT = '/Users/davidlu/code/arc-workspace/work/vscode-arclog/syntaxes';
const WORK = '/Users/davidlu/code/arc-workspace/work/arclog';
const SAMPLE = 100;

const files = {
  'source.arclog': path.join(EXT, 'arclog.tmLanguage.json'),
  'source.arcscene': path.join(EXT, 'arcscene.tmLanguage.json'),
};

const KEYWORDS = new Set([
  'INPUT', 'OUTPUT', 'RULE', 'DET', 'DET_OR_RULE', 'RULE_OR_DET', 'INIT', 'CHOOSE',
  'RIGID_DET', 'ALTS', 'ALT', 'DEMONSTRATED', 'DEMO_RULE', 'APPROXIMATED',
  'OR', 'IF', 'ALL', 'NOT', 'END', 'ONE',
  'key', 'instance', 'for', 'from', 'never', 'count',
]);
const SCENE_KEYWORDS = new Set(['parse', 'RENDER', 'RIGID']);
const CONTAINERS = new Set(['INPUT', 'OUTPUT', 'ALTS', 'ALT', 'RIGID']);
const BUILTINS = new Set(['ex', 'color', 'number', 'ident']);
const TASK_SIDE = new Set(['ex_input', 'ex_output']);

// The head word of each list and whether the list stands at form level,
// keyed by the line and column of its head word.
function heads(text) {
  const out = new Map();
  const stack = []; // each entry: {formLevel, container}
  let line = 0, col = 0, i = 0;
  const lines = text.split('\n');
  for (line = 0; line < lines.length; line++) {
    const s = lines[line];
    for (col = 0; col < s.length; col++) {
      const c = s[col];
      if (c === ';' && s[col + 1] === ';') break;
      if (c === '"') {
        col++;
        while (col < s.length && s[col] !== '"') { if (s[col] === '\\') col++; col++; }
        continue;
      }
      if (c === '(') {
        const m = /^[A-Za-z_][A-Za-z0-9_]*/.exec(s.slice(col + 1));
        const head = m ? m[0] : null;
        const parent = stack[stack.length - 1];
        const formLevel = !parent || parent.container;
        stack.push({ container: formLevel && CONTAINERS.has(head) });
        if (head) out.set(`${line}:${col + 1}`, { head, formLevel });
      } else if (c === ')') stack.pop();
    }
  }
  return out;
}

const GENERIC = /^(variable\.other|support\.function\.lib)/;

function deepest(scopes, suffix) {
  for (let k = scopes.length - 1; k >= 1; k--) if (scopes[k].endsWith(suffix)) return scopes[k];
  return null;
}

async function main() {
  const wasm = fs.readFileSync(require.resolve('vscode-oniguruma/release/onig.wasm')).buffer;
  await onig.loadWASM(wasm);
  const registry = new vt.Registry({
    onigLib: Promise.resolve({
      createOnigScanner: (p) => new onig.OnigScanner(p),
      createOnigString: (s) => new onig.OnigString(s),
    }),
    loadGrammar: async (scope) => files[scope]
      ? vt.parseRawGrammar(fs.readFileSync(files[scope], 'utf8'), files[scope]) : null,
  });
  const arclog = await registry.loadGrammar('source.arclog');
  const scene = await registry.loadGrammar('source.arcscene');

  function tokenize(grammar, text) {
    let stack = vt.INITIAL;
    return text.split('\n').map((s, line) => {
      const r = grammar.tokenizeLine(s, stack);
      stack = r.ruleStack;
      return r.tokens.map((t) => ({ line, col: t.startIndex, text: s.slice(t.startIndex, t.endIndex), scopes: t.scopes }));
    });
  }

  const problems = [];
  let nTokens = 0, nKeywords = 0, nScene = 0, nCompared = 0;
  const seenScene = {};

  function check(file, grammar, isScene) {
    const text = fs.readFileSync(file, 'utf8');
    const hd = heads(text);
    const toks = tokenize(grammar, text);
    const flat = isScene ? tokenize(arclog, text) : null;
    const name = path.basename(file);
    toks.forEach((lineToks, line) => {
      for (const t of lineToks) {
        nTokens++;
        const word = t.text;
        const h = hd.get(`${t.line}:${t.col}`);
        const top = t.scopes[t.scopes.length - 1];
        const where = `${name}:${t.line + 1}:${t.col + 1} '${word}' [${t.scopes.slice(1).join(' ')}]`;
        const atHead = h && h.head === word;
        const afterRender = isScene && /\(RENDER\s$/.test(text.split('\n')[t.line].slice(0, t.col));
        let expect = null;
        if (isScene) {
          if (atHead && word === 'parse') expect = 'keyword.other.clause.arcscene';
          else if (atHead && (word === 'RENDER' || word === 'RIGID')) expect = 'storage.type.form.arcscene';
          else if (atHead && word === 'ALL') expect = h.formLevel ? 'keyword.control.constraint.arcscene' : 'keyword.control.logic.arclog';
          else if (atHead && BUILTINS.has(word)) expect = 'support.function.builtin.arcscene';
          else if ((atHead || afterRender) && TASK_SIDE.has(word)) expect = 'support.function.task-side.arcscene';
        }
        if (expect) {
          nScene++;
          seenScene[`${word}${word === 'ALL' ? (h.formLevel ? ' (constraint)' : ' (clause)') : ''}`] = top;
          if (top !== expect) problems.push(`scene construct: expected ${expect}: ${where}`);
          continue;
        }
        if (atHead && (KEYWORDS.has(word) || SCENE_KEYWORDS.has(word) || /^[A-Z][A-Z0-9]+(_[A-Z0-9]+)*$/.test(word))) {
          nKeywords++;
          if (!/^(keyword|storage)\./.test(top)) problems.push(`unscoped keyword: ${where}`);
        }
        if (isScene) {
          // an arclog construct: the same scope as the arclog grammar gives it
          for (let c = t.col; c < t.col + word.length; c++) {
            const ft = flat[line].find((x) => x.col <= c && c < x.col + x.text.length);
            const a = deepest(t.scopes, '.arclog'), b = deepest(ft.scopes, '.arclog');
            nCompared++;
            if (a !== b) { problems.push(`differs from arclog: ${where} vs [${ft.scopes.slice(1).join(" ")}] (${a} / ${b})`); break; }
          }
        }
      }
    });
  }

  const scenes = fs.readdirSync(WORK).filter((f) => f.endsWith('.arcscene')).sort();
  for (const f of scenes) check(path.join(WORK, f), scene, true);
  const gens = fs.readdirSync(path.join(WORK, 'gen')).filter((f) => f.endsWith('.arclog')).sort();
  const step = Math.max(1, Math.floor(gens.length / SAMPLE));
  const sample = gens.filter((_, k) => k % step === 0).slice(0, SAMPLE);
  for (const f of sample) check(path.join(WORK, 'gen', f), arclog, false);

  console.log(`files: ${scenes.length} arcscene, ${sample.length} of ${gens.length} arclog`);
  console.log(`tokens: ${nTokens}; keyword tokens: ${nKeywords}; scene-only tokens: ${nScene}; scene characters compared with arclog: ${nCompared}`);
  console.log('scene-only scopes seen:');
  for (const [k, v] of Object.entries(seenScene).sort()) console.log(`  ${k}: ${v}`);
  console.log(`problems: ${problems.length}`);
  for (const p of problems.slice(0, 60)) console.log('  ' + p);
  process.exitCode = problems.length ? 1 : 0;
}
main();
