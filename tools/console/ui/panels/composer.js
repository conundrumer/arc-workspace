/* The comment box under the feed. */
import { html } from "/vendor/htm-preact-standalone.module.js";

export function Composer({boxRef, enabled, canSend, placeholder, hint, value, onInput, onSend}){
  return html`<div id="composer" class=${enabled?"":"disabled"}>
    <textarea ref=${boxRef} aria-label="comment" disabled=${!enabled}
      placeholder=${placeholder} value=${value}
      onInput=${e=>onInput(e.target.value)}></textarea>
    <div class="hints">
      <span>${hint}</span>
      <span class="actions"><button class="primary" disabled=${!canSend} onClick=${onSend}>send</button></span>
    </div>
  </div>`;
}
