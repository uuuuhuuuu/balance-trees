// Same control surface as TracePlayer, with bounded recent history and a worker.
export class StreamPlayer {
  constructor(config, onChange, onError, onReady) {
    this.config = config; this.onChange = onChange; this.onError = onError;
    this.delay = 650; this.running = false; this.done = false; this.index = 0;
    this.streaming = true; this.workerBusy = false;
    this.ready = false; this.pendingPlay = false; this.pendingTarget = null;
    this.trace = { strategy: config.strategy, seed: config.seed, source: 'browser', frames: [], sequence: [], total_count: config.count ?? 0 };
    this.worker = new Worker(new URL('./large-worker.mjs', import.meta.url), { type: 'module' });
    this.worker.onmessage = ({ data }) => {
      if (data.type === 'error') { this.running = false; this.workerBusy = false; onError(data.message); this.notify(); return; }
      if (data.ready) { this.ready = true; this.trace.sequence = data.preview; this.trace.total_count = data.count; }
      this.running = data.running; this.done = data.done; this.workerBusy = false;
      this.trace.frames.push(data.frame);
      if (this.trace.frames.length > 128) this.trace.frames.shift();
      this.index = this.trace.frames.length - 1;
      if (data.ready) {
        onReady(this);
        if (this.pendingPlay) { this.pendingPlay = false; this.play(); }
        else if (this.pendingTarget) { const target = this.pendingTarget; this.pendingTarget = null; this.request(target); }
      }
      this.notify();
    };
    this.worker.onerror = event => { this.running = false; this.workerBusy = false; onError(event.message || 'The simulation worker could not start.'); };
    this.worker.postMessage({ type: 'init', config });
  }
  get playing() { return this.running; }
  get frame() { return this.trace.frames[this.index] ?? null; }
  notify() { this.onChange(this.frame, this.index, this.playing); }
  play() {
    if (!this.ready) { this.pendingPlay = true; this.running = true; this.notify(); return; }
    if (this.done && this.index === this.trace.frames.length - 1) return;
    this.running = true; this.worker.postMessage({ type: 'play', delay: this.delay }); this.notify();
  }
  pause() { this.running = false; this.pendingPlay = false; this.pendingTarget = null; this.worker.postMessage({ type: 'pause' }); this.notify(); }
  seek(index) { this.index = Math.max(0, Math.min(this.trace.frames.length - 1, index)); this.notify(); }
  step(delta = 1) {
    this.pause();
    if (delta < 0 || this.index < this.trace.frames.length - 1) this.seek(this.index + delta);
    else this.request('event');
  }
  request(target) {
    if (!this.ready) { this.pendingTarget = target; return; }
    if (!this.done) { this.workerBusy = true; this.worker.postMessage({ type: 'step', target }); }
  }
  nextInsertion() { this.pause(); this.request('settled'); }
  nextRotation() { this.pause(); this.request('rotate'); }
  setDelay(delay) { this.delay = delay; this.worker.postMessage({ type: 'speed', delay }); }
  dispose() { this.worker.terminate(); this.running = false; }
}
