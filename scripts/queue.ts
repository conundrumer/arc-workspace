#!/usr/bin/env bun
// Next TS solvers to port: unported files without an #incorrect tag,
// smallest first (--order size, default) or in name order (--order name).
// Size = gzipped bytes of the minified source, so comments, formatting,
// identifier names, and type annotations don't affect rank. Sizes are
// cached in scripts/.queue-cache keyed by mtime; only changed files are
// re-minified.
// With --json, prints the list as one JSON array of {id, size} objects in
// place of one row per task.
// Usage: queue.ts [-n COUNT | --all] [--order name|size] [--json]

import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const root = path.dirname(import.meta.dir);
const src = path.join(root, "..", "arc-synth-bun", "programs", "solvers");
const dl = path.join(root, "programs", "solvers");
const cachePath = path.join(import.meta.dir, ".queue-cache");

const usage = "usage: queue.sh [-n COUNT | --all] [--order name|size] [--json]";
let count = 1;
let all = false;
let order = "size";
let json = false;
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === "-n") count = Number(args[++i]);
  else if (args[i].startsWith("-n")) count = Number(args[i].slice(2));
  else if (args[i] === "--all") all = true;
  else if (args[i] === "--order") order = args[++i];
  else if (args[i] === "--json") json = true;
  else {
    console.error(usage);
    process.exit(2);
  }
}
if (!Number.isInteger(count) || count < 1 || !["name", "size"].includes(order)) {
  console.error(usage);
  process.exit(2);
}

type Entry = { mtime: string; size: number; incorrect: boolean };

const cache = new Map<string, Entry>();
if (fs.existsSync(cachePath)) {
  for (const line of fs.readFileSync(cachePath, "utf8").split("\n")) {
    if (!line) continue;
    const [id, mtime, size, incorrect] = line.split("\t");
    cache.set(id, { mtime, size: Number(size), incorrect: incorrect === "1" });
  }
}

const ids = fs
  .readdirSync(src)
  .filter((f) => f.endsWith(".ts"))
  .map((f) => f.slice(0, -3));

const fresh = new Map<string, Entry>();
const staleMtime = new Map<string, string>();
for (const id of ids) {
  const mtime = String(fs.statSync(path.join(src, id + ".ts")).mtimeMs);
  const hit = cache.get(id);
  if (hit && hit.mtime === mtime) fresh.set(id, hit);
  else staleMtime.set(id, mtime);
}

if (staleMtime.size > 0) {
  const result = await Bun.build({
    entrypoints: [...staleMtime.keys()].map((id) => path.join(src, id + ".ts")),
    root: src,
    minify: true,
  });
  if (!result.success) {
    console.error(...result.logs);
    process.exit(1);
  }
  for (const artifact of result.outputs) {
    const id = path.basename(artifact.path, ".js");
    const size = zlib.gzipSync(await artifact.text()).length;
    const head = fs
      .readFileSync(path.join(src, id + ".ts"), "utf8")
      .split("\n", 10)
      .join("\n");
    fresh.set(id, {
      mtime: staleMtime.get(id)!,
      size,
      incorrect: head.includes("#incorrect"),
    });
  }
  fs.writeFileSync(
    cachePath,
    [...fresh.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([id, e]) => `${id}\t${e.mtime}\t${e.size}\t${e.incorrect ? 1 : 0}`)
      .join("\n") + "\n",
  );
}

const listed = ids
  .map((id) => ({ id, ...fresh.get(id)! }))
  .filter((e) => !e.incorrect && !fs.existsSync(path.join(dl, e.id + ".dl")))
  .sort((a, b) =>
    order === "name"
      ? a.id.localeCompare(b.id)
      : a.size - b.size || a.id.localeCompare(b.id),
  )
  .slice(0, all ? undefined : count);
if (json) console.log(JSON.stringify(listed.map((e) => ({ id: e.id, size: e.size }))));
else listed.forEach((e) => console.log(String(e.size).padStart(5) + "  " + e.id));
