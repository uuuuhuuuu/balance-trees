# Rotation Lab showcase

The visualizer is separate from statistical benchmarking. Its snapshots and
explanations are deliberately expensive; no visual work runs inside experiments.

## Launch and host

For public GitHub hosting, follow [the GitHub Pages setup guide](github-pages.md).
The included workflow tests and deploys the browser-only website automatically.

```sh
# Python-backed website, with the repository's actual strategies.
PYTHONPATH=src python -m balance_trees.showcase --port 8000

# Export an exact Python run, then import this JSON through the website.
PYTHONPATH=src python -m balance_trees.showcase \
  --strategy halving --sequence '1,10,2,9,3,8,4,7,5,6' \
  --seed 2026 --export benchmarks/results/halving-trace.json

# Serve the standalone browser showcase on any static host.
python -m http.server --directory src/balance_trees/showcase/site/dist 8000
```

After installation, `balance-tree-showcase` is also available. Static assets are
included in the Python package. There are no frontend dependencies, build steps,
CDNs, or external fonts. An HTTP origin is required for JavaScript modules.

The Python server provides `GET /api/config` and `POST /api/trace`. The latter
accepts `{"sequence":[1,2,3],"strategy":"halving","seed":2026}` and returns a
version 1 trace. On a static host, the viewer falls back to its browser simulator.
An API error after Python mode is selected is shown rather than silently
substituting a different simulation.

## Demonstrate a run

1. Choose the strategy, input family, key count, and seed; click **Build experiment**.
2. Use **Play**, the timeline, or individual event controls. **Next rotation** stops
   after one primitive rotation; **Next insertion** stops when a key is settled.
3. Watch left/right edges, promotion and demotion colors, and the explanation.
   The frame before a rotation identifies the involved nodes and middle subtree.
4. Click an input key to jump to that insertion. Drag the canvas to pan, use
   the zoom controls, and click **Fit** to restore automatic fitting.
5. Choose dark/light mode from the sidebar. **Tutorial** opens the short guide;
   it appears once on a new browser profile. The page contains only the visualizer.

Space toggles playback; left/right arrows step when a form control is not focused.
The player respects reduced-motion preferences when moving nodes.

For custom input, paste `8, 4, 12, -2, 0, 8` and click **Use sequence**, or import
an equivalent `.csv` / `.txt` file. Whitespace around numbers is accepted.
Empty fields, nonintegers, and unsafe JavaScript integers produce an explanatory
error. Duplicates are visualized as skipped insertions. There is no 64-key run
limit: larger inputs automatically switch to worker-backed playback.

Treap priority labels are scaled to [0, 1) for display; comparisons use 32-bit
priorities, with the key breaking ties. This reference treap intentionally stores
priority information outside the plain tree. Generating a priority consumes 32
logical bits; it is not an implementation of the theoretical optimized bit bound.

The browser uses a seeded xorshift32 generator, whereas Python uses its seeded
standard-library generator. Equal seeds do not imply equal trees across engines.
Export an exact trace when reproducibility across hosting modes matters.

## Large runs and speed

Enter `1000000` in **Keys**, choose a strategy and preset, click **Build**, then
select **Fast-forward** and **Play**. Counts are not limited by the input widget.
Preset sequences are generated in the worker; large CSV files are parsed there
as well. No million-element input list is rendered into the page.

Runs above 128 entries use typed-array tree storage and a Web Worker. The canvas
shows a connected window of at most 96 nodes near the current operation; its
visible root may be an internal node of the full tree. The toolbar reports the
number shown. Node count, height, mean depth, rotations, and random-bit counters
refer to the **entire tree**, not just this window. Cached subtree sizes/heights
are visualization metadata, separate from the metadata-free benchmark trees.

The full tree needs O(n) memory; replay history is bounded to 128 recent views.
The timeline and Back button inspect those recent views. Restart rebuilds the
run from its original seed. Full-history JSON export and arbitrary insertion
jumps are available in detailed mode; large-run JSON export is disabled rather
than exporting an incomplete history. The input chips show only a short preview.

**10×**, **100×**, and **Fast-forward** are additional speed options. Fast-forward
batches operations in short worker time slices and sends occasional snapshots
so pause, rebuild, theme changes, and the rest of the interface stay responsive.
Small runs also batch timeline events when fast-forwarding.

Memory allocation and algorithm complexity remain real limits. The worker checks
an estimated 512 MiB memory budget and uses signed 32-bit node indices; practical
browser limits may be lower. Million-key treaps and plain BSTs have been exercised
in the tests/manual checks. A full upward-walk strategy on a degenerate input can
still require quadratic work. Speed settings skip display delays, not the rule's
required decisions or rotations. Plain BSTs use known insertion boundaries when
available to avoid repeating an unnecessary search; resulting structures match
ordinary insertion. This viewer is not a wall-clock benchmark.

## Use another implementation

The renderer and player consume snapshots, not algorithm code. There are two
extension paths:

- **Python strategy:** implement the normal strategy protocol and use
  `context.choose(...)` and `context.promote(...)`. `TraceContext` observes those
  primitives without changing their decisions. Register the strategy to expose
  it to the Python trace API. Add its display label to the frontend flavor catalog.
- **Independent implementation:** emit the JSON contract below and import the
  file. Unknown strategy names are displayed as imported implementations.
  The renderer does not need a matching built-in simulator.

Top-level fields:

```json
{
  "schema_version": 1,
  "strategy": "my-tree",
  "seed": 2026,
  "sequence": [8],
  "source": "external",
  "frames": []
}
```

`frames` must contain at least one frame. Each frame has:

```json
{
  "kind": "settled",
  "title": "Insertion complete",
  "description": "Key 8 is now the root.",
  "insertion": 1,
  "key": 8,
  "focus": 8,
  "root": 8,
  "nodes": [{"key": 8, "left": null, "right": null, "priority": null}],
  "heap_valid": null,
  "stats": {
    "nodes": 1, "height": 0, "mean_depth": 0,
    "rotations": 0, "visits": 0, "random_bits": 0,
    "insertion_rotations": 0
  }
}
```

Keys identify nodes across snapshots. Child links and `root` are keys or `null`.
Every frame must describe a complete, acyclic BST. Depth counts edges. Global
counters are cumulative; `insertion_rotations` resets for the next insertion.

Recommended event kinds are `ready`, `begin`, `compare`, `insert`, `coin`,
`prepare`, `rotate`, `priority`, `duplicate`, and `settled`. Emit `settled` at the
end of each insertion to support insertion jumps. For a rotation add `promoted`,
`demoted`, `middle` (key or null), and `direction` (`left` or `right`). For a
coin add `numerator` and `denominator` as decimal strings, `purpose` (`rotate`
or `continue`), and boolean `outcome`. Strings avoid large-denominator precision
loss. Keep `heap_valid` null unless the implementation uses a priority heap.

Detailed imported traces support up to 128 entries, 20,000 frames, and 64 MiB. The viewer validates
ordering, links, cycles, node counts, and numeric statistics before playback.

## Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
node tests/test_showcase_browser.mjs
node tests/test_large_showcase.mjs
```

Tests compare traced Python runs with ordinary execution, including exact
rotation counts and random-bit consumption. Browser model tests cover all seven
strategies and input families, treap heap ordering, trace validation, CSV input,
backward stepping, jumps, and automatic stopping. Native browser layout testing
requires an environment where browser processes and networking are permitted.
