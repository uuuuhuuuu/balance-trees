"""Combine disjoint benchmark sizes without rerunning or replacing old trials."""

import argparse
import json
from pathlib import Path

from .benchmark import summarize, write_csv


def merge_runs(sources: list[Path], output: Path) -> dict:
    if len(sources) < 2:
        raise ValueError("Provide at least two benchmark run directories.")
    runs = [json.loads((source / "results.json").read_text()) for source in sources]
    metadata = dict(runs[0]["metadata"])
    variable = {"sizes", "started_at", "finished_at", "wall_seconds", "batches"}
    settings = {key: value for key, value in metadata.items() if key not in variable}
    sizes = set()
    batches = []
    records = []
    for run in runs:
        meta = run["metadata"]
        if settings != {
            key: value for key, value in meta.items() if key not in variable
        }:
            raise ValueError(
                "Runs must use the same machine, interpreter and settings."
            )
        if sizes.intersection(meta["sizes"]):
            raise ValueError(
                "Run sizes must be disjoint; existing trials are preserved."
            )
        sizes.update(meta["sizes"])
        batches.extend(meta.get("batches", [meta]))
        records.extend(run["trials"])
    metadata.update(
        sizes=sorted(sizes),
        started_at=min(batch["started_at"] for batch in batches),
        finished_at=max(batch["finished_at"] for batch in batches),
        wall_seconds=sum(batch["wall_seconds"] for batch in batches),
        batches=batches,
    )
    results = {"metadata": metadata, "summaries": summarize(records), "trials": records}
    # Validate all inputs before creating a fresh destination.
    output.mkdir(parents=True, exist_ok=False)
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    (output / "config.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (output / "trials.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in records)
    )
    write_csv(output / "summary.csv", results["summaries"])
    write_csv(
        output / "trials.csv",
        [
            {
                **{key: value for key, value in row.items() if key != "metrics"},
                **row["metrics"],
            }
            for row in records
        ],
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        merge_runs(args.input, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Combined measurements ready in {args.output}")


if __name__ == "__main__":
    main()
