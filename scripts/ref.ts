// Run the reference TS solver of one task on the grid on stdin, and print
// the output grid: one row per line, cells separated by spaces, 0 as `.`.
//
//   bun scripts/ref.ts <task_id> < grid.txt
//
// The grid is rows of digits, with `.` for 0, spaces and commas optional,
// and `#` lines skipped, or a JSON array of rows.

import { resolve } from "node:path";

const taskId = process.argv[2];
if (!taskId) {
  console.error("usage: bun scripts/ref.ts <task_id> < grid");
  process.exit(2);
}

const text = (await Bun.stdin.text()).trim();
let grid: number[][];
if (text.startsWith("[")) {
  grid = JSON.parse(text);
} else {
  grid = text
    .split("\n")
    .filter((line) => line.trim() && !line.trimStart().startsWith("#"))
    .map((line) =>
      [...line.replace(/[\s,]/g, "")].map((ch) => (ch === "." ? 0 : Number(ch))),
    );
}
if (!grid.length || !grid[0].length || grid.some((row) => row.length !== grid[0].length)) {
  console.error("bad grid");
  process.exit(2);
}

const path = resolve(import.meta.dir, "../../arc-synth-bun/programs/solvers", `${taskId}.ts`);
let solve: (input: number[][], palette: number[]) => number[][];
try {
  ({ solve } = await import(path));
} catch {
  console.error(`no reference solver for ${taskId}`);
  process.exit(2);
}

let out: number[][];
try {
  out = solve(grid, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
} catch (e) {
  console.error(`the reference solver threw: ${e}`);
  process.exit(1);
}
if (!out || !out.length) {
  console.log("undefined");
} else {
  for (const row of out) console.log(row.map((c) => (c === 0 ? "." : String(c))).join(" "));
}
