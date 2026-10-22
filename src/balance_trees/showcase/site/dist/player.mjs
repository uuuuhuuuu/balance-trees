// Playback is independent of the simulator and renderer.
export class TracePlayer {
  constructor(onChange = () => {}) { this.onChange = onChange; this.trace = null; this.index = 0; this.timer = null; this.delay = 650; }
  load(trace) { this.pause(); this.trace = trace; this.index = 0; this.notify(); }
  get playing() { return this.timer !== null; }
  get frame() { return this.trace?.frames[this.index] ?? null; }
  notify() { this.onChange(this.frame, this.index, this.playing); }
  seek(index) { if (!this.trace) return; this.index = Math.max(0, Math.min(this.trace.frames.length - 1, index)); if (this.index === this.trace.frames.length - 1) this.pause(); this.notify(); }
  step(delta = 1) { this.pause(); this.seek(this.index + delta); }
  nextInsertion() {
    this.pause(); if (!this.trace) return;
    let index = this.index + 1;
    while (index < this.trace.frames.length - 1 && this.trace.frames[index].kind !== 'settled') index++;
    this.seek(index);
  }
  nextRotation() {
    this.pause(); if (!this.trace) return;
    let index = this.index + 1;
    while (index < this.trace.frames.length - 1 && this.trace.frames[index].kind !== 'rotate') index++;
    this.seek(index);
  }
  play() {
    if (!this.trace || this.playing) return;
    if (this.index === this.trace.frames.length - 1) this.index = 0;
    const batch = this.delay === 0 ? Math.max(1, Math.ceil(this.trace.frames.length / 100)) : 1;
    this.timer = setInterval(() => this.seek(this.index + batch), this.delay === 0 ? 16 : this.delay); this.notify();
  }
  pause() { if (this.timer !== null) clearInterval(this.timer); this.timer = null; this.notify(); }
  setDelay(delay) { const wasPlaying = this.playing; this.pause(); this.delay = delay; if (wasPlaying) this.play(); }
}
