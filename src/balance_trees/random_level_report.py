"""Publish a separate random-level v2 policy and paired benchmark report."""

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

from .benchmark import summarize, write_csv
from .benchmark_report import CHARTS, CSS, chart_svg, esc, number, page

METRICS = ("mean_rotations", "mean_depth", "height", "mean_visits")
DATA_DIRECTORY = "random-level-v2-results"
REPORT_FILENAME = "random-level-v2.html"
LINK = '<a href="./random-level-v2.html">Random-level v2 · report</a>'
REQUEST_FIELDS = ("n", "trial", "order_seed", "seed")


def comparison_results(source: Path, baseline: Path) -> dict:
    """Pair raw records by their exact input and rotation seeds, never by row order."""
    metadata = json.loads((source / "config.json").read_text())
    provenance = json.loads((source / "comparison-config.json").read_text())
    if (
        hashlib.sha256(baseline.read_bytes()).hexdigest()
        != provenance["original_sha256"]
    ):
        raise ValueError("The original dataset checksum does not match the comparison.")
    if metadata["strategies"] != ["random-level-v2"]:
        raise ValueError("Expected a random-level-v2 validation batch.")
    original = json.loads(baseline.read_text())

    def identity(row):
        return (row["order"], *(row[key] for key in REQUEST_FIELDS))

    indexed = {
        identity(row): row
        for row in original["trials"]
        if row["strategy"] == "random-level"
    }
    revised, paired, seen = [], [], set()
    with (source / "trials.csv").open(newline="") as handle:
        for values in csv.DictReader(handle):
            if values["strategy"] != "random-level-v2":
                raise ValueError("Every new trial must use random-level-v2.")
            row = {
                "strategy": values["strategy"],
                "order": values["order"],
                **{key: int(values[key]) for key in REQUEST_FIELDS},
                "status": values["status"],
                "metrics": {
                    key: float(value)
                    for key, value in values.items()
                    if key
                    not in (*REQUEST_FIELDS, "strategy", "order", "status", "detail")
                    and value not in (None, "")
                },
            }
            key = identity(row)
            if key in seen or key not in indexed:
                raise ValueError(
                    "Trials must have unique, matching baseline input and rotation seeds."
                )
            seen.add(key)
            revised.append(row)
            paired.append(indexed[key])
    expected = {
        (order, n, trial)
        for order in metadata["orders"]
        for n in metadata["sizes"]
        for trial in range(metadata["trials"])
    }
    if {(r["order"], r["n"], r["trial"]) for r in revised} != expected:
        raise ValueError("The new trial matrix does not match its configuration.")
    records = paired + revised
    return {
        "metadata": {
            **metadata,
            "strategies": ["random-level", "random-level-v2"],
            "comparison": provenance,
            "original_metadata": original["metadata"],
            "comparison_note": "Operation counts and final shapes only; recorded in separate batches. No cross-version timing comparison.",
        },
        "summaries": summarize(records),
        "trials": records,
    }


def comparison_table(rows: list[dict]) -> str:
    columns = [
        ("strategy", "Version"),
        ("n", "Keys"),
        ("status", "Status"),
        ("completed_trials", "Trials"),
        ("mean_rotations", "Rot/key"),
        ("mean_rotations_se", "Rot SE"),
        ("max_rotations", "Max rot"),
        ("mean_depth", "Mean depth"),
        ("height", "Mean height"),
        ("mean_visits", "Decisions / steps per key"),
        ("mean_random_bits", "Bits/key"),
    ]
    parts = [
        '<div class="table-wrap" tabindex="0" role="region" aria-label="Paired measurements"><table><caption>Paired trials; depths and heights count edges. Max rotations is the maximum across completed trials.</caption><thead><tr>'
    ]
    parts.extend(f'<th scope="col">{label}</th>' for _, label in columns)
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for key, _ in columns:
            value = row.get(key)
            text = esc(value) if isinstance(value, str) else number(value)
            if key == "n":
                text = f"{value:,}"
            if key == "completed_trials":
                text = f"{value}/{row['requested_trials']}"
            parts.append(f"<td>{text}</td>")
        parts.append("</tr>")
    return "".join(parts) + "</tbody></table></div>"


DESCRIPTION = """<section id="policy"><h2>What changes in v2</h2>
<p>The original policy samples a target level near log₂(n), then rotates the new leaf all the way there. Its cost is max(0, insertion depth &minus; target). A growing gap between the actual search path and that idealized level causes growing rotation counts.</p>
<p>V2 keeps the same 64-bit sampler, count and priority extrema. It changes how the tree is repaired:</p>
<ol><li>Choose a repair level using the previous priority interval, then update the count and extrema.</li>
<li>A strict new minimum priority promotes the inserted leaf to the root. A new maximum stays a leaf.</li>
<li>For other insertions above or at the chosen level, do nothing. If the leaf is one edge below it, rotate once.</li>
<li>Otherwise walk to the ancestor two edges below the repair level. A straight path promotes its parent once; a bent path promotes the selected ancestor twice.</li></ol>
<p>The selected subtree root reaches the repair level; the inserted leaf need not reach it. Equal priorities are not strict records. Duplicate keys consume no bits or rotations.</p>
<details><summary>Why expected rotations are below three</summary>
<p>Assume an initially empty tree and independent uniformly distributed priority rolls. With k previous successful insertions, a strict new minimum occurs with probability at most 1/(k+1), including finite-priority ties. It costs at most k rotations; every other insertion costs at most two.</p>
<pre>R ≤ 2 + k · indicator(strict new minimum)
E[R] ≤ 2 + k/(k+1) &lt; 3</pre>
<p>This expectation is over the whole priority history. It is not a worst-case limit of two or three rotations, or a bound conditioned on every possible existing tree. Rare record insertions can still take a full path of rotations.</p></details>
<p class="notice">The rotation bound does not guarantee logarithmic depth or constant rebalancing time. Walking to the repair can take O(h) ancestor steps; sampling uses O(log n) integer-band iterations. No priorities or sizes are added to nodes.</p>
</section>"""


SCRIPT = """<script>const control=document.getElementById('workload');control.addEventListener('change',()=>{for(const section of document.querySelectorAll('[data-workload]'))section.hidden=control.value!=='all'&&section.dataset.workload!==control.value;});control.value='random';control.dispatchEvent(new Event('change'));</script>"""


def generate_v2_report(
    source: Path, baseline: Path, description: Path, output: Path
) -> None:
    results = comparison_results(source, baseline)
    documentation = description.read_text()
    meta, rows = results["metadata"], results["summaries"]
    output.mkdir(parents=True, exist_ok=True)
    data = output / DATA_DIRECTORY
    data.mkdir(exist_ok=True)
    for name in (
        "config.json",
        "summary.csv",
        "trials.csv",
        "comparison.csv",
        "comparison-config.json",
    ):
        shutil.copyfile(source / name, data / name)
    (data / "description.md").write_text(documentation, encoding="utf-8")
    (data / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    write_csv(data / "paired-summary.csv", rows)
    (output / "report.css").write_text(CSS, encoding="utf-8")
    stats = (
        '<div class="stats">'
        + "".join(
            f'<div class="stat"><strong>{esc(value)}</strong><span>{label}</span></div>'
            for value, label in (
                (f"{max(meta['sizes']):,}", "largest instance"),
                (
                    f"{meta['trials']} + {meta['trials']}",
                    "paired trials per size and workload",
                ),
                (len(meta["orders"]), "input families"),
                (
                    f"{sum(r['status'] == 'complete' for r in results['trials'])} / {len(results['trials'])}",
                    "completed paired trial records",
                ),
            )
        )
        + "</div>"
    )
    highlights = {
        r["strategy"]: r
        for r in rows
        if r["n"] == max(meta["sizes"])
        and r["order"] == "random"
        and r["status"] == "complete"
    }
    highlight = ""
    if len(highlights) == 2:
        old, revised = highlights["random-level"], highlights["random-level-v2"]
        highlight = f'<p class="notice">At {old["n"]:,} random keys: <strong>{number(old["mean_rotations"])} → {number(revised["mean_rotations"])} rotations per key</strong>, original to v2, across {meta["trials"]} paired trials per version. This measured result is separate from the expected rotation proof below.</p>'
    sections = []
    for order in meta["orders"]:
        figures = []
        for metric in METRICS:
            filename = f"{order}-{metric}.svg"
            (data / filename).write_text(
                chart_svg(results, order, metric), encoding="utf-8"
            )
            figures.append(
                f'<figure class="chart"><img src="./{DATA_DIRECTORY}/{filename}" alt="{esc(order)}: {esc(CHARTS[metric])}" loading="lazy"><a href="./{DATA_DIRECTORY}/{filename}" download>Download SVG</a></figure>'
            )
        sections.append(
            f'<section data-workload="{esc(order)}"><h2>{esc(order.capitalize())} sequences</h2><div class="charts">{"".join(figures)}</div><details class="panel"><summary>Every paired measurement for {esc(order)}</summary>{comparison_table([r for r in rows if r["order"] == order])}</details></section>'
        )
    options = '<option value="all">All workloads</option>' + "".join(
        f'<option value="{esc(order)}">{esc(order.capitalize())}</option>'
        for order in meta["orders"]
    )
    downloads = (
        '<section id="downloads"><h2>Reports and source data</h2><div class="downloads">'
        + "".join(
            f'<a href="./{DATA_DIRECTORY}/{filename}" download>{label}</a>'
            for filename, label in (
                ("description.md", "Full policy documentation"),
                ("results.json", "All paired records · JSON"),
                ("paired-summary.csv", "Paired summaries · CSV"),
                ("trials.csv", "Every v2 trial · CSV"),
                ("config.json", "V2 machine and methodology"),
                ("comparison-config.json", "Pairing and baseline checksum"),
            )
        )
        + '</div><p class="status-note">Raw records retain their original timings for inspection. The comparative graphs and tables show operation counts and tree shapes; no cross-version timing comparison is made.</p></section>'
    )
    body = f"""<header><span class="eyebrow">Rotation Lab / policy and measured comparison</span><h1>Random-level v2</h1><p class="lede">A local repair at a sampled level, with fewer than three expected rotations per insertion under independent uniform rolls from empty. Compare the original policy and v2 from {min(meta["sizes"]):,} to {max(meta["sizes"]):,} keys.</p><div class="downloads"><a href="#policy">Read the policy</a><a href="#reports">Explore the reports</a></div></header>
{stats}{highlight}{DESCRIPTION}<section id="reports"><h2>Original vs v2: paired reports</h2><p>Both versions use the same input and rotation seeds for each paired trial. The original records are selected from the archived dataset; v2 was measured in a separate batch. No recorded original result is replaced.</p>
<p class="meta">V2 batch: {esc(meta["cpu"])} · Python {esc(meta["python"].split()[0])} · {esc(meta["finished_at"])} · seed {meta["seed"]}.</p>
<div class="workload"><label for="workload">Input family</label><select id="workload">{options}</select></div><p class="status-note">Dashed gray: log₂(n), an unscaled numeric guide behind every measured curve. Logarithmic x scale; y uses log(1 + value). Whiskers show ±1 standard error. Only fully completed groups are plotted; tables retain incomplete statuses.</p></section>
{"".join(sections)}{downloads}<section><h2>How the comparison was recorded</h2><p>{esc(meta["comparison"]["pairing"])}</p><p>Each completed tree passes ordering, parent-link, cycle and complete key-set checks. Standard errors are across trial seeds, conditional on the fixed input permutation. V2 decisions / steps include ancestor visits; the original policy has no such decision visits. Maximum rotations can exceed two because strict new minima still reach the root.</p><p>Finite depth and height results do not prove a balance guarantee. The linked documentation contains the derivation, limits, exact policy steps and reproduction commands.</p></section>"""
    (output / REPORT_FILENAME).write_text(
        page("Random-level v2 reports", body, script=SCRIPT), encoding="utf-8"
    )
    # Add navigation links without regenerating historical reports or measurements.
    for filename in ("index.html", "results.html", "summary.html", "random-level.html"):
        existing = output / filename
        if existing.is_file():
            text = existing.read_text()
            if 'href="./random-level-v2.html"' not in text:
                existing.write_text(
                    text.replace(
                        '<a href="./summary.html">',
                        LINK + '<a href="./summary.html">',
                        1,
                    ),
                    encoding="utf-8",
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path("benchmarks/random-level-v2")
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(
            "src/balance_trees/showcase/site/dist/random-level-results/results.json"
        ),
    )
    parser.add_argument(
        "--description", type=Path, default=Path("docs/random-level-v2.md")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        generate_v2_report(args.input, args.baseline, args.description, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(f"V2 policy and reports: {args.output / REPORT_FILENAME}")


if __name__ == "__main__":
    main()
