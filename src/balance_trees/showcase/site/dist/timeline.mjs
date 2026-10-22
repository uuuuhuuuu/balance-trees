// Render only visible rows, even when a detailed trace contains 20,000 events.
export const EVENT_ROW_HEIGHT = 44;
export function visibleEventRange(count, scrollTop, height) {
  const start = Math.max(0, Math.min(count, Math.floor(scrollTop / EVENT_ROW_HEIGHT) - 2));
  return [start, Math.min(count, start + Math.ceil(height / EVENT_ROW_HEIGHT) + 5)];
}

export class EventTimeline {
  constructor(container, onSelect) {
    this.container = container;
    this.items = container.firstElementChild;
    this.frames = []; this.index = -1;
    container.addEventListener('scroll', () => this.draw(), { passive: true });
    // Select on press: a playback update can replace a row before mouseup.
    container.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      const row = event.target.closest('button[data-index]');
      if (!row) return;
      event.preventDefault();
      const index = Number(row.dataset.index);
      onSelect(index);
      this.items.querySelector(`[data-index="${index}"]`)?.focus({ preventScroll: true });
    });
    container.addEventListener('click', event => {
      if (event.detail > 0) return; // Pointer presses were already handled.
      const row = event.target.closest('button[data-index]');
      if (row) onSelect(Number(row.dataset.index));
    });
    container.addEventListener('keydown', event => {
      const delta = { ArrowDown: 1, ArrowUp: -1, PageDown: 4, PageUp: -4 }[event.key];
      if (delta === undefined && event.key !== 'Home' && event.key !== 'End') return;
      if (!this.frames.length) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? this.frames.length - 1
        : Math.max(0, Math.min(this.frames.length - 1, this.index + delta));
      onSelect(next);
      this.reveal(next); this.draw();
      this.items.querySelector(`[data-index="${next}"]`)?.focus({ preventScroll: true });
    });
  }
  update(frames, index) {
    const reset = this.frames !== frames;
    const changed = reset || this.index !== index || this.last !== frames.at(-1);
    this.frames = frames; this.index = index; this.last = frames.at(-1);
    this.items.style.height = `${frames.length * EVENT_ROW_HEIGHT}px`;
    if (reset) this.container.scrollTop = 0;
    if (changed) this.reveal(index);
    this.draw();
  }
  reveal(index) {
    const top = index * EVENT_ROW_HEIGHT, height = this.container.clientHeight || 176;
    if (top < this.container.scrollTop) this.container.scrollTop = top;
    else if (top + EVENT_ROW_HEIGHT > this.container.scrollTop + height) this.container.scrollTop = top + EVENT_ROW_HEIGHT - height;
  }
  draw() {
    const [start, end] = visibleEventRange(this.frames.length, this.container.scrollTop, this.container.clientHeight || 176);
    const document = this.container.ownerDocument;
    const focused = this.items.contains(document.activeElement) ? document.activeElement.dataset.index : null;
    const rows = [];
    for (let index = start; index < end; index++) {
      const frame = this.frames[index], row = document.createElement('button');
      row.type = 'button'; row.className = 'event-entry'; row.dataset.index = index; row.dataset.kind = frame.kind;
      row.style.top = `${index * EVENT_ROW_HEIGHT}px`;
      row.setAttribute('aria-label', `Event ${index + 1}: ${frame.title}. Insertion ${frame.insertion}.`);
      if (index === this.index) row.setAttribute('aria-current', 'step');
      for (const [className, text] of [['event-entry-number', index + 1], ['event-marker', ''], ['event-entry-title', frame.title], ['event-entry-insertion', `#${frame.insertion}`]]) {
        const label = document.createElement('span'); label.className = className; label.textContent = text;
        if (className === 'event-marker') label.setAttribute('aria-hidden', 'true');
        row.append(label);
      }
      row.title = `${frame.title}\n${frame.description}`;
      rows.push(row);
    }
    this.items.replaceChildren(...rows);
    if (focused !== null) this.items.querySelector(`[data-index="${focused}"]`)?.focus({ preventScroll: true });
  }
}

// The progress bar seeks directly on press/drag instead of relying on the
// browser's range-track paging behavior. Resume playback only after release.
export class TimelineScrubber {
  constructor(slider, getPlayer) {
    this.slider = slider; this.getPlayer = getPlayer; this.drag = null;
    slider.addEventListener('pointerdown', event => {
      if (event.button !== 0 || this.drag) return;
      const player = getPlayer();
      if (!player.trace?.frames.length) return;
      event.preventDefault();
      this.drag = { player, playing: player.playing, pointerId: event.pointerId };
      player.pause();
      slider.focus({ preventScroll: true });
      slider.setPointerCapture(event.pointerId);
      this.move(event);
    });
    slider.addEventListener('pointermove', event => this.move(event));
    slider.addEventListener('pointerup', event => {
      if (event.pointerId !== this.drag?.pointerId) return;
      this.move(event); this.finish();
    });
    for (const type of ['pointercancel', 'lostpointercapture']) slider.addEventListener(type, event => {
      if (event.pointerId === this.drag?.pointerId) this.finish();
    });
    slider.addEventListener('input', () => {
      if (this.drag) return;
      const player = getPlayer(), playing = player.playing;
      player.pause(); player.seek(Number(slider.value), { animate: false });
      this.resume(player, playing);
    });
  }
  move(event) {
    if (event.pointerId !== this.drag?.pointerId) return;
    const player = this.drag.player;
    if (player !== this.getPlayer()) { this.finish(); return; }
    const { left, width } = this.slider.getBoundingClientRect();
    // Match the 16px thumb so both endpoints remain reachable.
    const ratio = Math.max(0, Math.min(1, (event.clientX - left - 8) / Math.max(1, width - 16)));
    player.seek(Math.round(ratio * (player.trace.frames.length - 1)), { animate: false });
  }
  finish() {
    if (!this.drag) return;
    const { player, playing, pointerId } = this.drag;
    this.drag = null;
    if (this.slider.hasPointerCapture(pointerId)) this.slider.releasePointerCapture(pointerId);
    this.resume(player, playing);
  }
  resume(player, playing) {
    const more = player.streaming ? !player.done : player.index < player.trace.frames.length - 1;
    if (playing && player === this.getPlayer() && more) player.play();
  }
}
