// preact 10.29.8 with its hooks, and htm 3.1.1, joined here. htm's own
// standalone build carries a preact from 2022 whose diff rewrote every
// option's value on every render, which redrew an open select popup.
import { h } from "./preact.module.js";
import htm from "./htm.module.js";
export * from "./preact.module.js";
export * from "./hooks.module.js";
export const html = htm.bind(h);
