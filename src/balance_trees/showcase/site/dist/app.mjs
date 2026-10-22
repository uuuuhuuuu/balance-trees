import { FLAVORS, ORDERS, makeSequence, parseSequence, simulate, validateTrace } from './model.mjs';
import { TracePlayer } from './player.mjs';
import { detectEngine } from './runtime.mjs';
import { initialTheme, readPreference, savePreference, THEME_KEY, TUTORIAL_KEY, TUTORIAL_STEPS } from './interface.mjs';
import { DETAIL_LIMIT } from './large-model.mjs';
import { StreamPlayer } from './stream-player.mjs';
import { EventTimeline } from './timeline.mjs';

const $ = id => document.getElementById(id);
const svgNS = 'http://www.w3.org/2000/svg';
const stage = $('tree-stage'), viewport = $('viewport');
let pythonAvailable = false, generation = 0, request = null;
let orderLabel = 'Increasing', autoFit = true, animationId = null;
let camera = { x: 0, y: 0, scale: 1 }, positions = new Map();
const nodeElements = new Map(), edgeElements = new Map();
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
let player = new TracePlayer(render);
const eventTimeline = new EventTimeline($('event-history'), index => { player.pause(); player.seek(index); });
let preferences;
try { preferences = window.localStorage; } catch { /* Optional storage. */ }
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $('theme-toggle').textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
  $('theme-toggle').setAttribute('aria-pressed', String(theme === 'dark'));
  document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#12161e' : '#f5f6f8';
}
applyTheme(initialTheme(preferences, window.matchMedia('(prefers-color-scheme: dark)').matches));
$('theme-toggle').addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  applyTheme(theme); savePreference(preferences, THEME_KEY, theme);
});
let tutorialStep = 0;
function renderTutorial() {
  const step = TUTORIAL_STEPS[tutorialStep];
  $('tutorial-progress').textContent = `${tutorialStep + 1} / ${TUTORIAL_STEPS.length}`;
  $('tutorial-step-title').textContent = step.title;
  $('tutorial-description').textContent = step.text;
  $('tutorial-back').disabled = tutorialStep === 0;
  $('tutorial-next').textContent = tutorialStep === TUTORIAL_STEPS.length - 1 ? 'Done' : 'Next';
}
function openTutorial() { player.pause(); tutorialStep = 0; renderTutorial(); $('tutorial').showModal(); }
$('tutorial-open').addEventListener('click', openTutorial);
$('tutorial-close').addEventListener('click', () => $('tutorial').close());
$('tutorial-back').addEventListener('click', () => { tutorialStep--; renderTutorial(); });
$('tutorial-next').addEventListener('click', () => {
  if (tutorialStep === TUTORIAL_STEPS.length - 1) $('tutorial').close();
  else { tutorialStep++; renderTutorial(); }
});
$('tutorial').addEventListener('close', () => savePreference(preferences, TUTORIAL_KEY, 'yes'));

for (const [value, info] of Object.entries(FLAVORS)) $('strategy').add(new Option(info.name, value));
for (const [value, name] of Object.entries(ORDERS)) $('order').add(new Option(name, value));

function svgElement(tag, attributes = {}) {
  const element = document.createElementNS(svgNS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  return element;
}
function error(message = '') { $('error').textContent = message; $('error').hidden = !message; }
function validSeed() {
  const seed = Number($('seed').value);
  if (!$('seed').value.trim() || !Number.isInteger(seed) || seed < 0 || seed > 4294967295) throw new Error('Seed must be an integer from 0 to 4294967295.');
  return seed;
}
function layout(frame) {
  const keys = player.streaming ? frame.nodes.map(node => node.key) : player.trace.sequence;
  const ranks = new Map([...new Set(keys)].sort((a, b) => a - b).map((key, index) => [key, index]));
  const nodes = new Map(frame.nodes.map(node => [node.key, node]));
  const result = new Map(), stack = frame.root === null ? [] : [[frame.root, 0]];
  while (stack.length) {
    const [key, depth] = stack.pop(), node = nodes.get(key);
    result.set(key, { x: ranks.get(key) * 76, y: depth * 90 });
    if (node.left !== null) stack.push([node.left, depth + 1]);
    if (node.right !== null) stack.push([node.right, depth + 1]);
  }
  return result;
}
function fittedCamera(target) {
  const width = stage.clientWidth, height = stage.clientHeight;
  if (!target.size) return { x: width / 2, y: height / 2, scale: 1 };
  const xs = [...target.values()].map(point => point.x), ys = [...target.values()].map(point => point.y);
  const minX = Math.min(...xs) - 42, maxX = Math.max(...xs) + 42;
  const minY = Math.min(...ys) - 42, maxY = Math.max(...ys) + 48;
  const scale = Math.min(1.15, (width - 70) / (maxX - minX), (height - 85) / (maxY - minY));
  return { scale, x: width / 2 - (minX + maxX) / 2 * scale, y: (height - 15) / 2 - (minY + maxY) / 2 * scale };
}
function syncElements(frame) {
  const keys = new Set(frame.nodes.map(node => node.key));
  for (const [key, element] of nodeElements) if (!keys.has(key)) { element.remove(); nodeElements.delete(key); }
  const edgeKeys = new Set();
  for (const node of frame.nodes) {
    let group = nodeElements.get(node.key);
    if (!group) {
      group = svgElement('g', { class: 'tree-node', 'data-key': node.key });
      group.append(svgElement('circle', { r: 23 }), svgElement('text', { class: 'node-label' }), svgElement('text', { class: 'priority-label', y: 37 }), svgElement('title'));
      group.children[1].textContent = node.key;
      $('nodes').append(group); nodeElements.set(node.key, group);
    }
    group.setAttribute('class', ['tree-node', frame.focus === node.key ? 'focus' : '', frame.promoted === node.key ? 'promoted' : '', frame.demoted === node.key ? 'demoted' : '', frame.middle === node.key ? 'middle' : ''].filter(Boolean).join(' '));
    group.children[2].textContent = node.priority === null ? '' : `p ${(node.priority / 4294967296).toFixed(3)}`;
    group.children[3].textContent = node.priority === null ? `Key ${node.key}` : `Key ${node.key}; full priority ${node.priority}`;
    for (const [side, child] of [['L', node.left], ['R', node.right]]) if (child !== null) {
      const id = `${node.key}:${child}`; edgeKeys.add(id);
      if (!edgeElements.has(id)) {
        const edge = svgElement('g', { class: 'tree-edge' });
        edge.append(svgElement('path'), svgElement('text'));
        edge.children[1].textContent = side; $('edges').append(edge); edgeElements.set(id, edge);
      }
    }
  }
  for (const [key, element] of edgeElements) if (!edgeKeys.has(key)) { element.remove(); edgeElements.delete(key); }
}
function paint(frame, points, view) {
  viewport.setAttribute('transform', `translate(${view.x} ${view.y}) scale(${view.scale})`);
  for (const [key, point] of points) nodeElements.get(key)?.setAttribute('transform', `translate(${point.x} ${point.y})`);
  for (const node of frame.nodes) {
    const parent = points.get(node.key);
    for (const [side, child] of [['L', node.left], ['R', node.right]]) if (child !== null) {
      const end = points.get(child), edge = edgeElements.get(`${node.key}:${child}`);
      const middleY = (parent.y + end.y) / 2;
      edge.children[0].setAttribute('d', `M ${parent.x} ${parent.y + 23} C ${parent.x} ${middleY} ${end.x} ${middleY} ${end.x} ${end.y - 24}`);
      edge.children[1].setAttribute('x', (parent.x + end.x) / 2 + (side === 'L' ? -9 : 9));
      edge.children[1].setAttribute('y', parent.y + 52);
    }
  }
}
function draw(frame, animate = true) {
  if (animationId !== null) cancelAnimationFrame(animationId);
  syncElements(frame);
  const target = layout(frame), startPoints = new Map(), targetCamera = autoFit ? fittedCamera(target) : { ...camera };
  const startCamera = { ...camera };
  for (const [key, point] of target) {
    const parent = frame.nodes.find(node => node.left === key || node.right === key);
    startPoints.set(key, positions.get(key) ?? positions.get(parent?.key) ?? point);
  }
  const duration = animate && !reducedMotion.matches ? Math.min(420, player.delay * .72) : 0;
  const start = performance.now();
  function tick(now) {
    const progress = duration ? Math.min(1, (now - start) / duration) : 1;
    const eased = 1 - (1 - progress) ** 3;
    positions = new Map([...target].map(([key, end]) => {
      const begin = startPoints.get(key);
      return [key, { x: begin.x + (end.x - begin.x) * eased, y: begin.y + (end.y - begin.y) * eased }];
    }));
    camera = Object.fromEntries(['x', 'y', 'scale'].map(key => [key, startCamera[key] + (targetCamera[key] - startCamera[key]) * eased]));
    paint(frame, positions, camera);
    animationId = progress < 1 ? requestAnimationFrame(tick) : null;
  }
  animationId = requestAnimationFrame(tick);
}
function render(frame, index, playing) {
  if (!frame || !player.trace) return;
  const trace = player.trace, flavor = FLAVORS[trace.strategy];
  $('tree-name').textContent = flavor?.name ?? String(trace.strategy ?? 'Imported tree');
  $('order-name').textContent = orderLabel;
  $('source-badge').textContent = trace.source === 'python' ? 'Python implementation' : trace.source === 'browser' ? 'Browser simulation' : 'Imported trace';
  $('visible-count').textContent = frame.windowed ? `${frame.nodes.length} / ${frame.stats.nodes.toLocaleString()} nodes shown` : '';
  $('strategy-note').textContent = flavor?.note ?? 'This implementation supplies its own snapshots and explanations through the common trace format.';
  $('phase').textContent = ({ ready: 'Ready', begin: 'Search', compare: 'Compare', insert: 'Leaf placed', priority: 'Priority', scan: 'Recount', coin: 'Decision', prepare: 'Before rotation', rotate: 'After rotation', settled: 'Settled', duplicate: 'Duplicate' })[frame.kind] ?? frame.kind;
  $('event-title').textContent = frame.title; $('event-description').textContent = frame.description;
  $('insertion-number').textContent = String(frame.insertion).padStart(2, '0');
  $('current-key').textContent = frame.key === null ? 'No key yet' : `Key ${frame.key}`;
  $('event-index').textContent = `${index + 1} / ${trace.frames.length}${player.streaming ? ' recent' : ''}`;
  $('timeline').max = trace.frames.length - 1; $('timeline').value = index;
  $('event-history').setAttribute('aria-label', player.streaming ? 'Recent snapshots: scroll and click to inspect' : 'Event history: scroll and click to inspect');
  eventTimeline.update(trace.frames, index);
  $('play-label').textContent = playing ? 'Pause' : index === trace.frames.length - 1 && (!player.streaming || player.done) ? 'Replay' : 'Play';
  $('play-symbol').textContent = playing ? 'Ⅱ' : '▶';
  $('play').setAttribute('aria-label', playing ? 'Pause animation' : 'Play animation');
  $('previous').disabled = index === 0;
  for (const id of ['next', 'next-rotation', 'next-insertion']) $(id).disabled = index === trace.frames.length - 1 && (!player.streaming || player.done);
  if (player.streaming && trace.strategy === 'none') $('next-rotation').disabled = true;
  const stats = frame.stats;
  for (const [id, name] of [['metric-nodes', 'nodes'], ['metric-height', 'height'], ['metric-rotations', 'rotations'], ['metric-visits', 'visits'], ['metric-bits', 'random_bits'], ['metric-insertion-rotations', 'insertion_rotations']]) $(id).textContent = stats[name];
  $('metric-scans').textContent = stats.scanned_nodes ?? 0;
  $('metric-depth').textContent = stats.mean_depth.toFixed(2);
  $('heap-row').hidden = frame.heap_valid === null;
  $('heap-status').textContent = frame.heap_valid ? 'Preserved' : 'Rebalancing';
  $('heap-icon').textContent = frame.heap_valid ? '✓' : '↻';
  $('coin-detail').hidden = frame.kind !== 'coin';
  if (frame.kind === 'coin') {
    $('coin-purpose').textContent = frame.purpose === 'continue' ? 'CONTINUATION PROBABILITY' : frame.purpose === 'select-root' ? 'ROOT SELECTION PROBABILITY' : 'ROTATION PROBABILITY';
    $('coin-probability').textContent = `${frame.numerator} / ${frame.denominator}`;
    $('coin-outcome').textContent = frame.outcome ? 'Coin outcome: yes' : 'Coin outcome: no';
  }
  const settled = frame.kind === 'settled' ? frame.insertion : Math.max(0, frame.insertion - 1);
  $('sequence-progress').textContent = `${settled.toLocaleString()} / ${(trace.total_count ?? trace.sequence.length).toLocaleString()} inserted`;
  for (const [i, chip] of [...$('sequence-chips').children].entries()) {
    chip.classList.toggle('done', i < settled);
    chip.classList.toggle('current', i === frame.insertion - 1);
  }
  $('empty-tree').hidden = frame.nodes.length > 0;
  $('priority-legend').hidden = !frame.nodes.some(node => node.priority !== null);
  $('svg-description').textContent = `${frame.title}. ${frame.description} ${stats.nodes} nodes, height ${stats.height}.`;
  draw(frame);
}
function setInputChips(trace) {
  $('input-label').textContent = player.streaming ? `Input (first ${trace.sequence.length})` : 'Input';
  $('sequence-chips').replaceChildren();
  trace.sequence.forEach((key, index) => {
    const chip = document.createElement('button'); chip.className = 'key-chip'; chip.type = 'button';
    chip.textContent = key; chip.title = `Jump to insertion ${index + 1}: ${key}`;
    chip.disabled = Boolean(player.streaming);
    if (!player.streaming) chip.addEventListener('click', () => { player.pause(); player.seek(trace.frames.findIndex(frame => frame.insertion === index + 1)); });
    $('sequence-chips').append(chip);
  });
}
function load(trace, label) {
  validateTrace(trace);
  player.pause(); player.dispose?.();
  player = new TracePlayer(render); player.setDelay(Number($('speed').value));
  orderLabel = label; autoFit = true; positions = new Map();
  $('export-trace').disabled = false;
  $('export-trace').title = '';
  setInputChips(trace); player.load(trace);
}
function startStream(config, autoplay = false) {
  player.pause(); player.dispose?.();
  autoFit = true; positions = new Map();
  orderLabel = ORDERS[config.order ?? 'custom'];
  $('export-trace').disabled = true;
  $('export-trace').title = 'Large runs retain recent frames only. Full trace export is available for detailed runs.';
  $('source-badge').textContent = 'Preparing worker…';
  const runner = new StreamPlayer(config,
    (...args) => { if (player === runner) render(...args); },
    message => { if (player === runner) error(message); },
    ready => {
      if (player !== ready) return;
      $('count').value = ready.trace.total_count;
      setInputChips(ready.trace);
      if (autoplay) ready.play();
    });
  player = runner; runner.setDelay(Number($('speed').value));
}
async function build(custom = false) {
  const token = ++generation; request?.abort(); player.pause(); error();
  try {
    const seed = validSeed(), strategy = $('strategy').value;
    const order = custom ? 'custom' : $('order').value;
    const count = Number($('count').value);
    const text = $('sequence').value;
    let entries = 1;
    if (order === 'custom') for (const char of text) { if (char === ',') entries++; if (entries > DETAIL_LIMIT) break; }
    if ((order !== 'custom' && count > DETAIL_LIMIT) || (order === 'custom' && entries > DETAIL_LIMIT)) {
      $('order').value = order; $('count').disabled = order === 'custom';
      startStream({ strategy, seed, order, ...(order === 'custom' ? { text } : { count }) });
      if (order !== 'custom') $('sequence').value = '';
      return;
    }
    const sequence = order === 'custom' ? parseSequence($('sequence').value) : makeSequence(order, Number($('count').value), seed);
    let trace;
    if (pythonAvailable) {
      request = new AbortController();
      const response = await fetch(new URL('./api/trace', document.baseURI), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sequence, strategy, seed }), signal: request.signal });
      const payload = await response.json(); if (!response.ok) throw new Error(payload.error ?? 'The Python trace could not be generated.'); trace = payload;
    } else trace = simulate(sequence, strategy, seed);
    if (token !== generation) return;
    $('sequence').value = sequence.join(', '); $('order').value = order; $('count').disabled = order === 'custom'; $('count').value = sequence.length;
    load(trace, ORDERS[order]);
  } catch (failure) { if (failure.name !== 'AbortError' && token === generation) error(failure.message); }
}
function download(text, filename, type) {
  const url = URL.createObjectURL(new Blob([text], { type })), anchor = document.createElement('a');
  anchor.href = url; anchor.download = filename; document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('generate').addEventListener('click', () => build());
$('use-sequence').addEventListener('click', () => build(true));
$('order').addEventListener('change', () => { $('count').disabled = $('order').value === 'custom'; });
$('import-sequence').addEventListener('click', () => $('sequence-file').click());
$('sequence-file').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 65536) {
      generation++; request?.abort(); error();
      $('order').value = 'custom'; $('count').disabled = true; $('sequence').value = '';
      startStream({ strategy: $('strategy').value, seed: validSeed(), file }); return;
    }
    const text = await file.text(); parseSequence(text); $('sequence').value = text; await build(true);
  } catch (failure) { error(failure.message); }
  finally { event.target.value = ''; }
});
$('import-trace').addEventListener('click', () => $('trace-file').click());
$('trace-file').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 64 * 1024 * 1024) throw new Error('Detailed trace files must be smaller than 64 MiB.');
    const trace = validateTrace(JSON.parse(await file.text()));
    generation++; request?.abort(); player.pause(); error();
    $('sequence').value = trace.sequence.join(', '); $('order').value = 'custom'; $('count').value = trace.sequence.length; $('count').disabled = true;
    if (Object.hasOwn(FLAVORS, trace.strategy)) $('strategy').value = trace.strategy;
    load(trace, 'Imported sequence');
  } catch (failure) { error(failure.message); }
  finally { event.target.value = ''; }
});
$('export-trace').addEventListener('click', () => { if (player.trace) download(JSON.stringify(player.trace), `rotation-lab-${String(player.trace.strategy).replace(/[^a-z0-9-]/gi, '_')}.json`, 'application/json'); });
function togglePlayback() {
  if (player.streaming && player.done) startStream(player.config, true);
  else if (player.playing) player.pause();
  else player.play();
}
$('play').addEventListener('click', togglePlayback);
$('restart').addEventListener('click', () => {
  if (player.streaming) startStream(player.config);
  else { player.pause(); player.seek(0); }
});
$('previous').addEventListener('click', () => player.step(-1));
$('next').addEventListener('click', () => player.step());
$('next-rotation').addEventListener('click', () => player.nextRotation());
$('next-insertion').addEventListener('click', () => player.nextInsertion());
$('timeline').addEventListener('input', event => { player.pause(); player.seek(Number(event.target.value)); });
$('speed').addEventListener('change', event => player.setDelay(Number(event.target.value)));
function zoom(factor) {
  if (!player.frame) return;
  if (animationId !== null) cancelAnimationFrame(animationId);
  autoFit = false;
  const center = { x: stage.clientWidth / 2, y: stage.clientHeight / 2 };
  const scale = Math.max(.03, Math.min(4, camera.scale * factor)), ratio = scale / camera.scale;
  camera = { scale, x: center.x - (center.x - camera.x) * ratio, y: center.y - (center.y - camera.y) * ratio };
  paint(player.frame, positions, camera);
}
$('zoom-in').addEventListener('click', () => zoom(1.25));
$('zoom-out').addEventListener('click', () => zoom(.8));
$('fit').addEventListener('click', () => { autoFit = true; if (player.frame) draw(player.frame); });
let drag = null;
stage.addEventListener('pointerdown', event => {
  if (event.target.closest('button') || event.button !== 0) return;
  if (animationId !== null) cancelAnimationFrame(animationId);
  drag = { x: event.clientX, y: event.clientY, camera: { ...camera } }; autoFit = false;
  stage.classList.add('dragging'); stage.setPointerCapture(event.pointerId);
});
stage.addEventListener('pointermove', event => {
  if (!drag || !player.frame) return;
  camera.x = drag.camera.x + event.clientX - drag.x; camera.y = drag.camera.y + event.clientY - drag.y;
  paint(player.frame, positions, camera);
});
for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) stage.addEventListener(event, () => { drag = null; stage.classList.remove('dragging'); });
stage.addEventListener('wheel', event => { if (event.ctrlKey || event.metaKey) { event.preventDefault(); zoom(event.deltaY < 0 ? 1.1 : 1 / 1.1); } }, { passive: false });
new ResizeObserver(() => { if (player.frame) draw(player.frame, false); }).observe(stage);
document.addEventListener('keydown', event => {
  if ($('tutorial').open) return;
  if (event.target.closest('input,select,textarea,button,a,summary')) return;
  if (event.code === 'Space') { event.preventDefault(); togglePlayback(); }
  if (event.code === 'ArrowRight') { event.preventDefault(); player.step(); }
  if (event.code === 'ArrowLeft') { event.preventDefault(); player.step(-1); }
});
const engineMode = document.querySelector('meta[name="rotation-lab-engine"]')?.content ?? 'auto';
pythonAvailable = await detectEngine(document.baseURI, engineMode) === 'python';
await build();
if (!readPreference(preferences, TUTORIAL_KEY)) openTutorial();
