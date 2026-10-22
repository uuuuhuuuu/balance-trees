// Small presentation preferences; simulation and playback remain independent.
export const THEME_KEY = 'rotation-lab:theme';
export const TUTORIAL_KEY = 'rotation-lab:tutorial-seen';

export function readPreference(storage, key) {
  try { return storage?.getItem(key) ?? null; } catch { return null; }
}

export function savePreference(storage, key, value) {
  try { storage?.setItem(key, value); } catch { /* Preferences are optional. */ }
}

export function initialTheme(storage, prefersDark) {
  const saved = readPreference(storage, THEME_KEY);
  return saved === 'dark' || saved === 'light' ? saved : prefersDark ? 'dark' : 'light';
}

export const TUTORIAL_STEPS = [
  { title: 'Build a run', text: 'Choose a strategy, sequence, number of keys, and seed. Select Build to reset the run. Equal seeds replay the same run within the same engine.' },
  { title: 'Control playback', text: 'Click or drag the timeline bar to jump instantly; running playback resumes on release. Scroll the event list and click a row to pause and inspect it. Play, pause, step, or jump to the next rotation or insertion. Choose up to 100× speed or Fast-forward to batch events. Small runs keep their full history; larger runs keep 128 recent views. Restart rebuilds the run from its seed.' },
  { title: 'Read a rotation', text: 'Smaller keys go left and larger keys go right. Cyan marks focus, orange marks promotion, pink marks demotion, and dashed violet marks the middle subtree. A rotation changes parent links while preserving key order. Drag to pan and use Fit or the zoom buttons to inspect the tree.' },
  { title: 'Use your own input', text: 'Paste comma-separated integers such as 8, 4, 12, -2, 0, or import a CSV/text file. Presets and CSV inputs support millions of entries, subject to browser memory. Large runs show a window of at most 96 nodes with exact global statistics. Use Fast-forward; slow or degenerate strategies can still take substantial time. Full JSON traces are for detailed runs of up to 128 entries.' },
  { title: 'Themes and shortcuts', text: 'Switch dark/light mode using the sidebar button. Space plays or pauses; left/right arrows step when a form control is not focused. Reopen this tutorial at any time. Treaps use priorities; the experimental BST strategies do not store them.' },
];
