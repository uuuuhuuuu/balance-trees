import './random-level-v3.mjs';
import { LargeTree } from './large-model.mjs';

let engine = null, running = false, done = false, delay = 650, target = null, scheduled = null;
let lastReport = 0;
function report(extra = {}) {
  postMessage({ type: 'frame', frame: engine.snapshot(), done, running, ...extra });
}
function schedule(wait = 0) {
  if (scheduled === null) scheduled = setTimeout(tick, wait);
}
function tick() {
  scheduled = null;
  if (!engine || done || (!running && !target)) return;
  try {
    const start = performance.now();
    const fast = delay === 0 && running;
    let steps = 0;
    while (steps++ < (fast || target ? 50000 : 1)) {
      if (!engine.advance()) { done = true; running = false; target = null; break; }
      const reached = target === 'event' || target === engine.current.kind;
      if (target && reached) { target = null; break; }
      if (performance.now() - start >= 35) break;
    }
    if (!running || done || performance.now() - lastReport >= 50 || !fast) {
      report(); lastReport = performance.now();
    }
    if (running || target) schedule(fast || target ? 0 : delay);
  } catch (error) { running = false; target = null; postMessage({ type: 'error', message: error.message }); }
}
self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'init') {
      const config = data.config;
      if (config.file) {
        if (config.file.size > 256 * 1024 * 1024) throw new Error('This CSV file exceeds the large-run memory budget. Try a smaller file.');
        config.text = await config.file.text(); delete config.file;
      }
      engine = new LargeTree(config); done = false; running = false; target = null;
      const preview = Array.from({ length: Math.min(32, engine.input.count) }, (_, i) => engine.input.at(i));
      report({ ready: true, count: engine.input.count, preview });
    } else if (data.type === 'play') {
      delay = data.delay; running = true; target = null; schedule();
    } else if (data.type === 'pause') {
      const active = running || target !== null;
      running = false; target = null; if (engine && active) report();
    } else if (data.type === 'step') {
      running = false; target = data.target; schedule();
    } else if (data.type === 'speed') { delay = data.delay; }
  } catch (error) { postMessage({ type: 'error', message: error.message }); }
};
