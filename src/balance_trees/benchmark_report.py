"""Generate portable SVG graphs and two static pages from local measurements."""

import argparse
import html
import json
import math
import shutil
from pathlib import Path

CHARTS = {
    "microseconds_per_insertion": "Insertion time (µs / key)",
    "mean_depth": "Final mean depth (edges)",
    "height": "Final height (edges)",
    "mean_rotations": "Rotations / key",
    "mean_visits": "Rebalance decisions / steps / key",
    "mean_random_bits": "Logical random bits / key",
    "mean_scanned_nodes": "Recount scans / key",
}
COLORS = [
    "#2563eb",
    "#d97706",
    "#7c3aed",
    "#475569",
    "#db2777",
    "#0891b2",
    "#dc2626",
    "#4d7c0f",
    "#059669",
    "#9333ea",
]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def number(value) -> str:
    if value is None:
        return "—"
    return f"{value:,.3g}"


def chart_svg(results: dict, order: str, metric: str) -> str:
    """Log x; rotations use a zoomed linear y-axis, others use log(1+y)."""
    meta = results["metadata"]
    sizes = sorted(meta["sizes"])
    complete = [
        r
        for r in results["summaries"]
        if r["order"] == order and r["status"] == "complete"
    ]
    max_value = max(
        (r[metric] + (r.get(metric + "_se") or 0) for r in complete), default=1
    )
    linear = metric == "mean_rotations"
    if linear:
        ymax = max(1, max_value) * 1.12
    else:
        ymax = max(1, max_value, math.log2(sizes[-1])) * 1.12
    left, top, width, height = 67, 46, 595, 233

    def x(n):
        return (
            left
            + (math.log(n) - math.log(sizes[0]))
            / max(1, math.log(sizes[-1]) - math.log(sizes[0]))
            * width
        )

    def y(value):
        if linear:
            fraction = max(0, value) / ymax
        else:
            fraction = math.log1p(max(0, value)) / math.log1p(ymax)
        return top + height * (1 - fraction)

    title = f"{order.capitalize()} · {CHARTS[metric]}"
    canvas_height = max(430, 345 + math.ceil(len(meta["strategies"]) / 3) * 22)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 690 {canvas_height}" role="img" aria-labelledby="title desc"><title id="title">{esc(title)}</title>',
        '<desc id="desc">Measured Python trials. Logarithmic key counts. Except for rotations, the vertical scale is log(1+y) and a dashed gray log2(n) reference is behind the measurements: an unscaled numeric guide, not a fitted bound or timing prediction. Rotations use a linear vertical scale focused on the measured range. Whiskers show one standard error. Only fully completed groups are plotted. Gaps are missing measurements.</desc>',
        "<style>text{font:12px system-ui,sans-serif;fill:#334155}.grid{stroke:#e2e8f0}path,line{vector-effect:non-scaling-stroke}</style>",
        f'<rect width="690" height="{canvas_height}" rx="14" fill="white"/>',
        f'<text x="22" y="26" style="font-size:15px;font-weight:650">{esc(title)}</text>',
    ]
    for tick in range(5):
        if linear:
            value = ymax * tick / 4
        else:
            value = math.expm1(math.log1p(ymax) * tick / 4)
        yy = y(value)
        parts += [
            f'<line class="grid" x1="{left}" x2="{left + width}" y1="{yy:.2f}" y2="{yy:.2f}"/>',
            f'<text x="{left - 9}" y="{yy + 4:.2f}" text-anchor="end">{number(value)}</text>',
        ]
    # Keep all grid lines and measurements, but leave room for million-key labels.
    label_count = min(len(sizes), 6)
    label_indices = {
        round(i * (len(sizes) - 1) / max(1, label_count - 1))
        for i in range(label_count)
    }
    for index, n in enumerate(sizes):
        parts += [
            f'<line class="grid" x1="{x(n):.2f}" x2="{x(n):.2f}" y1="{top}" y2="{top + height}"/>',
        ]
        if index in label_indices:
            parts.append(
                f'<text x="{x(n):.2f}" y="301" text-anchor="middle">{n:,}</text>'
            )
    # Sample the reference in data space before applying the nonlinear y scale.
    reference = []
    for step in range(101):
        n = math.exp(
            math.log(sizes[0]) + (math.log(sizes[-1]) - math.log(sizes[0])) * step / 100
        )
        reference.append(f"{'M' if step == 0 else 'L'}{x(n):.2f},{y(math.log2(n)):.2f}")
    if not linear:
        parts += [
            f'<path class="log-reference" d="{" ".join(reference)}" stroke="#94a3b8" stroke-width="3" stroke-dasharray="7 5" opacity="0.65" fill="none"><title>log₂(n): unscaled numeric reference, not a fitted bound or timing prediction</title></path>',
            f'<text x="{left + width - 6}" y="{y(math.log2(sizes[-1])) - 9:.2f}" text-anchor="end" style="fill:#64748b;font-size:11px">log₂(n) reference</text>',
        ]
    for index, strategy in enumerate(meta["strategies"]):
        color = (
            COLORS[index]
            if index < len(COLORS)
            else f"hsl({index * 137 % 360} 65% 37%)"
        )
        rows = {r["n"]: r for r in complete if r["strategy"] == strategy}
        previous = None
        for n in sizes:
            row = rows.get(n)
            if row is None:
                previous = None
                continue
            xx, yy = x(n), y(row[metric])
            if previous is not None:
                parts.append(
                    f'<path d="M{previous[0]:.2f},{previous[1]:.2f} L{xx:.2f},{yy:.2f}" stroke="{color}" stroke-width="2" fill="none"/>'
                )
            error = row.get(metric + "_se")
            if error is not None:
                lo, hi = y(row[metric] - error), y(row[metric] + error)
                parts.append(
                    f'<path d="M{xx:.2f},{lo:.2f}V{hi:.2f} M{xx - 3:.2f},{lo:.2f}h6 M{xx - 3:.2f},{hi:.2f}h6" stroke="{color}" fill="none"/>'
                )
            parts.append(
                f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="4" fill="{color}"><title>{esc(strategy)}; n={n}; {esc(metric)}={row[metric]:.6g}; SE={esc(error)}</title></circle>'
            )
            previous = xx, yy
        lx, ly = 22 + index % 3 * 223, 331 + index // 3 * 22
        parts.append(
            f'<circle cx="{lx}" cy="{ly}" r="4" fill="{color}"/><text x="{lx + 10}" y="{ly + 4}">{esc(strategy)}</text>'
        )
    if linear:
        axis_note = "x: log(keys) · y: linear · missing groups omitted · whiskers: ±1 SE"
    else:
        axis_note = "x: log(keys) · y: log(1 + value) · missing groups omitted · whiskers: ±1 SE"
    parts += [
        f'<text x="22" y="{canvas_height - 8}" style="font-size:10px">{axis_note}</text>',
        "</svg>",
    ]
    return "\n".join(parts)


CSS = """
:root{color-scheme:light;--ink:#18283b;--muted:#526275;--line:#dce3eb;--paper:#fff;--accent:#245fd0}
*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:var(--ink);font:14px/1.55 system-ui,sans-serif}
main{max-width:1440px;margin:auto;padding:28px 32px 60px}nav{display:flex;gap:22px;flex-wrap:wrap;margin-bottom:28px}
a{color:var(--accent);text-underline-offset:3px}h1{font-size:clamp(28px,4vw,42px);letter-spacing:-1.5px;line-height:1.15;margin:8px 0 14px}
h2{font-size:20px;margin:0 0 12px}h3{font-size:16px;margin:0 0 8px}.eyebrow{font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--accent);font-weight:700}
.lede{font-size:16px;max-width:880px;color:var(--muted)}.meta{color:var(--muted);font-size:12px}.stats,.cards,.charts{display:grid;gap:14px}.stats{grid-template-columns:repeat(4,1fr);margin:24px 0}.stat,.card,section,details.panel{border:1px solid var(--line);border-radius:12px;background:var(--paper);padding:20px}.stat strong{font-size:27px;display:block}.stat span{color:var(--muted)}
.cards{grid-template-columns:repeat(auto-fit,minmax(310px,1fr));margin:20px 0}.charts{grid-template-columns:repeat(2,minmax(0,1fr))}.chart img{width:100%;height:auto;display:block}.chart{margin:0;border:1px solid var(--line);border-radius:14px;overflow:hidden;background:white}.chart a{display:block;text-align:right;padding:0 16px 10px;font-size:12px}
section,details.panel{margin:20px 0}section section{border:none;padding:0}ul{padding-left:18px;margin:8px 0}li{margin:5px 0}summary{cursor:pointer;font-weight:650}details[open]>summary{margin-bottom:14px}.downloads{display:flex;gap:16px;flex-wrap:wrap}.table-wrap{overflow:auto;max-height:65vh}table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap;font-variant-numeric:tabular-nums}th,td{text-align:right;padding:7px 10px;border-bottom:1px solid var(--line)}th{background:#eef2f7;position:sticky;top:0;z-index:1}th:first-child,td:first-child{text-align:left}tbody tr:hover{background:#f1f5fb}.timeout,.error{color:#a03a16}.complete{color:#176841}.not_run{color:var(--muted)}.card p{color:var(--muted);font-size:12px}.card ul{font-size:12px}.workload{display:flex;align-items:center;gap:14px;margin:18px 0}select,button{font:inherit;padding:7px 10px;border:1px solid var(--line);border-radius:6px;background:white;color:var(--ink)}.unit{color:var(--muted)}code{font-size:12px;overflow-wrap:anywhere}pre{overflow:auto;background:#f0f4f8;padding:16px;border-radius:8px}.empty{padding:30px}.notice{border-left:3px solid #d97706;padding-left:12px}.status-note{font-size:12px;color:var(--muted)}
@media(max-width:750px){main{padding:20px 14px}.stats{grid-template-columns:repeat(2,1fr)}.charts{grid-template-columns:1fr}.cards{grid-template-columns:1fr}.stat,.card,section{padding:15px}}
@media print{body{background:white}main{max-width:none;padding:0}.table-wrap{max-height:none;overflow:visible}.charts{grid-template-columns:repeat(2,1fr)}nav,.downloads,.workload{display:none}details{break-inside:avoid}.card{break-inside:avoid}}
"""


def page(title: str, body: str, *, script: str = "") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Complete measured local benchmark results for experimental binary search tree strategies.">
<title>{esc(title)} · Rotation Lab</title><link rel="stylesheet" href="./report.css"></head><body><main>
<nav aria-label="Lab pages"><a href="./index.html">← Tree preview</a><a href="./results.html">Benchmark graphs</a><a href="./random-level.html">Random-level · thousands</a><a href="./random-level-scale.html">Random-level · millions</a><a href="./random-level-v2.html">Random-level v2 · report</a><a href="./summary.html">Compact results</a><a href="#downloads">Download all data</a></nav>
{body}</main>{script}</body></html>"""


def result_table(rows: list[dict], *, table_id: str = "all-results") -> str:
    columns = [
        ("strategy", "Strategy"),
        ("order", "Input"),
        ("n", "Keys"),
        ("status", "Status"),
        ("completed_trials", "Trials"),
        ("microseconds_per_insertion", "µs/key"),
        ("seconds", "Seconds"),
        ("mean_depth", "Mean depth"),
        ("mean_depth_se", "Depth SE"),
        ("height", "Height"),
        ("mean_insertion_depth", "Insertion depth"),
        ("mean_rotations", "Rot/key"),
        ("max_rotations", "Max rot"),
        ("mean_visits", "Decisions/key"),
        ("max_visits", "Max decisions"),
        ("mean_random_bits", "Bits/key"),
        ("max_random_bits", "Max bits"),
        ("mean_scanned_nodes", "Scans/key"),
        ("max_scanned_nodes", "Max scans"),
    ]
    parts = [
        f'<div class="table-wrap" tabindex="0" role="region" aria-label="Complete benchmark matrix"><table id="{table_id}"><caption>All strategy / workload / size groups. Blank metrics mean no completed trial; partial metrics describe completed trials only.</caption><thead><tr>'
    ]
    parts += [f'<th scope="col">{label}</th>' for _, label in columns]
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append(f'<tr data-order="{esc(row["order"])}">')
        for key, _ in columns:
            value = row.get(key)
            text = esc(value) if isinstance(value, str) else number(value)
            if key == "completed_trials":
                text = f"{value}/{row['requested_trials']}"
            if key == "status":
                text = f'<span class="{esc(row["status"])}">{esc(row["status"])}</span>'
            parts.append(f"<td>{text}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table></div>")
    return "".join(parts)


def common(results: dict) -> tuple[str, str]:
    meta, rows = results["metadata"], results["summaries"]
    complete = sum(r["status"] == "complete" for r in rows)
    completed_trials = sum(r["status"] == "complete" for r in results["trials"])
    stats = (
        '<div class="stats">'
        + "".join(
            f'<div class="stat"><strong>{esc(value)}</strong><span>{label}</span></div>'
            for value, label in [
                (
                    len(meta["strategies"]),
                    "Python strategies measured",
                ),
                (f"{max(meta['sizes']):,}", "largest sequence attempted"),
                (f"{complete} / {len(rows)}", "fully completed groups"),
                (
                    f"{completed_trials} / {len(results['trials'])}",
                    "completed / planned trials",
                ),
            ]
        )
        + "</div>"
    )
    machine = f'<p class="meta">{esc(meta["cpu"])} · {esc(meta["platform"])} · Python {esc(meta["python"].split()[0])} · {esc(meta["finished_at"])} · seed {meta["seed"]}</p>'
    statuses = {
        status: sum(r["status"] == status for r in results["trials"])
        for status in ("timeout", "not_run", "error")
    }
    coverage = f'<p class="status-note">Trial outcomes: {completed_trials} complete · {statuses["timeout"]} timed out · {statuses["not_run"]} not run after a group stopped · {statuses["error"]} errors. All records are included in the downloads.</p>'
    methodology = (
        "<section><h2>How to read these results</h2><ul>"
        + "".join(
            f"<li>{esc(meta[key])}</li>"
            for key in ("timing", "deadline", "sampling", "execution", "limits")
        )
        + f"<li>Each group requests {meta['trials']} trials. Deadline: {meta['timeout_seconds']:g} seconds per process. Root depth is zero; height counts edges. All completed trees pass ordering, parent-link, cycle and key-set checks.</li><li>Charts include fully completed groups only, with ±1 standard error where available. Timeout groups can have partial trial metrics in the full table and downloads. Missing data is never plotted as zero.</li></ul></section>"
    )
    return stats + machine + coverage, methodology


def generate_report(
    source: Path,
    output: Path,
    *,
    random_level: bool = False,
    random_level_scale: bool = False,
) -> None:
    if random_level and random_level_scale:
        raise ValueError("Choose one dedicated random-level report.")
    random_level = random_level or random_level_scale
    results = json.loads((source / "results.json").read_text())
    meta, rows = results["metadata"], results["summaries"]
    if random_level and meta["strategies"] != ["random-level"]:
        raise ValueError("The random-level page requires a random-level-only run.")
    output.mkdir(parents=True, exist_ok=False)
    data_name = "random-level-results" if random_level else "results"
    if random_level_scale:
        data_name = "random-level-scale-results"
    data = output / data_name
    data.mkdir(exist_ok=True)
    for filename in (
        "results.json",
        "config.json",
        "summary.csv",
        "trials.csv",
        "trials.jsonl",
    ):
        if (source / filename).resolve() != (data / filename).resolve():
            shutil.copyfile(source / filename, data / filename)
    (output / "report.css").write_text(CSS, encoding="utf-8")
    downloads = (
        '<section id="downloads"><h2>Every result, ready to inspect</h2><div class="downloads">'
        + "".join(
            f'<a href="./{data_name}/{filename}" download>{label}</a>'
            for filename, label in [
                ("results.json", "Full JSON"),
                ("summary.csv", "All group summaries · CSV"),
                ("trials.csv", "Every trial · CSV"),
                ("trials.jsonl", "Append-only trial records"),
                ("config.json", "Machine, seeds & methodology"),
            ]
        )
        + "</div></section>"
    )
    memory_note = ""
    if random_level_scale and (source / "memory.json").exists():
        memory = json.loads((source / "memory.json").read_text())
        if (source / "memory.json").resolve() != (data / "memory.json").resolve():
            shutil.copyfile(source / "memory.json", data / "memory.json")
        peak = memory["peak_child_rss_bytes"] / 1024**2
        cap = memory["address_space_limit_bytes"] / 1024**2
        memory_note = (
            f'<p class="status-note">Largest trial peak resident memory: {peak:,.1f} MiB, '
            f'including final invariant validation. Per-process address-space cap: {cap:,.0f} MiB. '
            f'<a href="./{data_name}/memory.json" download>Download memory record</a>.</p>'
        )
    stats, methodology = common(results)
    cards = []
    for strategy in meta["strategies"]:
        spec = meta["catalog"][strategy]
        bullets = []
        for order in meta["orders"]:
            group = [
                r for r in rows if r["strategy"] == strategy and r["order"] == order
            ]
            full = [r for r in group if r["status"] == "complete"]
            if not full:
                bullets.append(
                    f"<li><strong>{esc(order)}</strong>: no complete group; see trial statuses.</li>"
                )
                continue
            row = max(full, key=lambda r: r["n"])
            larger = [r for r in group if r["n"] > row["n"]]
            suffix = (
                "; larger sizes: "
                + ", ".join(f"{r['n']:,} {r['status']}" for r in larger)
                if larger
                else ""
            )
            bullets.append(
                f"<li><strong>{esc(order)}</strong> · {row['n']:,} keys: <b>{number(row['microseconds_per_insertion'])} µs/key</b>; depth {number(row['mean_depth'])} ± {number(row.get('mean_depth_se'))}; height {number(row['height'])}; rot {number(row['mean_rotations'])}/key; decisions {number(row['mean_visits'])}/key; scans {number(row['mean_scanned_nodes'])}/key{esc(suffix)}.</li>"
            )
        cards.append(
            f'<article class="card"><h3>{esc(spec["name"])} <span class="unit">· {esc(strategy)}</span></h3><p>{esc(spec["note"])}</p><ul>{"".join(bullets)}</ul></article>'
        )
    summary = f'<header><span class="eyebrow">Rotation Lab / measured on this computer</span><h1>All strategies. All results.</h1><p class="lede">Compact findings for every strategy and input family. Each bullet uses the largest fully completed sequence for that strategy; different key counts are printed explicitly.</p></header>{stats}<p class="notice">A timeout means the process hit its deadline. It supplies no completed runtime or final tree measurement. No strategy is silently dropped.</p><div class="cards">{"".join(cards)}</div><details class="panel"><summary>All {len(rows)} groups · every size and status</summary>{result_table(rows)}</details>{downloads}{methodology}'
    if not random_level:
        (output / "summary.html").write_text(
            page("All results", summary), encoding="utf-8"
        )
    sections = []
    for index, order in enumerate(meta["orders"]):
        figures = []
        for metric, title in CHARTS.items():
            filename = f"{order}-{metric}.svg"
            (data / filename).write_text(
                chart_svg(results, order, metric), encoding="utf-8"
            )
            figures.append(
                f'<figure class="chart"><img src="./{data_name}/{filename}" alt="{esc(order)}: {esc(title)}" loading="lazy"><a href="./{data_name}/{filename}" download>Download SVG</a></figure>'
            )
        sections.append(
            f'<section data-workload="{esc(order)}"><h2>{esc(order.capitalize())} sequences</h2><div class="charts">{"".join(figures)}</div><details class="panel"><summary>Measurements for {esc(order)}</summary>{result_table([r for r in rows if r["order"] == order], table_id=f"table-{index}")}</details></section>'
        )
    options = '<option value="all">All workloads</option>' + "".join(
        f'<option value="{esc(o)}">{esc(o.capitalize())}</option>'
        for o in meta["orders"]
    )
    script = """<script>const control=document.getElementById('workload');control.addEventListener('change',()=>{for(const section of document.querySelectorAll('[data-workload]'))section.hidden=control.value!=='all'&&section.dataset.workload!==control.value;});control.value='random';control.dispatchEvent(new Event('change'));</script>"""
    dashboard = f'<header><span class="eyebrow">Rotation Lab / local benchmarks</span><h1>How the strategies scale</h1><p class="lede">Real Python measurements from {min(meta["sizes"]):,} to {max(meta["sizes"]):,} keys. Compare time, shape and work as sequences grow. All charts are downloadable SVGs.</p></header>{stats}<div class="workload"><label for="workload">Input family</label><select id="workload">{options}</select></div><p class="status-note">Logarithmic x scale. Other charts use log(1 + value), so zeros remain visible; rotations use a linear scale focused on the measured range. Whiskers show ±1 standard error. Missing points indicate incomplete groups; open the measurement tables for statuses.</p>{"".join(sections)}{downloads}{methodology}'
    reference_note = '<p class="status-note">Every graph except rotations has a muted dashed log₂(n) curve behind the measurements. It is an unscaled numeric reference, not a fitted bound or timing prediction; metric units remain as labelled.</p>'
    dashboard = dashboard.replace(
        '<div class="workload">', reference_note + '<div class="workload">', 1
    )
    if random_level:
        dashboard = dashboard.replace(
            "How the strategies scale", "Random-level at thousands of keys"
        ).replace(
            "Compare time, shape and work as sequences grow.",
            f"{meta['trials']} independently seeded trials per size and input family measure the random-level heuristic. Finite measurements do not establish logarithmic balance.",
        )
    if random_level_scale:
        dashboard = dashboard.replace(
            "Random-level at thousands of keys", "Random-level through millions of keys"
        )
        if meta["trials"] == 1:
            dashboard = dashboard.replace(
                "1 independently seeded trials per size and input family measure",
                "One deterministic trial per size and input family (no standard error) measures",
            )
        dashboard = dashboard.replace(
            '<div class="workload">', memory_note + '<div class="workload">', 1
        )
    filename = "random-level.html" if random_level else "results.html"
    if random_level_scale:
        filename = "random-level-scale.html"
    title = "Random-level benchmarks" if random_level else "Benchmark graphs"
    (output / filename).write_text(
        page(title, dashboard, script=script), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    focused = parser.add_mutually_exclusive_group()
    focused.add_argument(
        "--random-level",
        action="store_true",
        help="write a dedicated random-level.html page and separate data downloads",
    )
    focused.add_argument(
        "--random-level-scale",
        action="store_true",
        help="write random-level-scale.html with separate large-sweep graphs and data",
    )
    args = parser.parse_args()
    try:
        generate_report(
            args.input,
            args.output,
            random_level=args.random_level,
            random_level_scale=args.random_level_scale,
        )
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(f"Report ready in {args.output}")


if __name__ == "__main__":
    main()
