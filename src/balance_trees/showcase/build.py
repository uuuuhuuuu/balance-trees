"""Prepare a browser-only static website for GitHub Pages or another host."""

import argparse
import json
import shutil
from pathlib import Path

from ..strategies import strategy_factory
from .server import STATIC

ENGINE_META = '<meta name="rotation-lab-engine" content="auto">'


def catalog_source() -> str:
    catalog = {
        "treap": {
            "name": "Treap",
            "tag": "Priority heap",
            "note": "A BST by key and min-heap by stored random priority. This browser reference retains per-node priorities.",
        },
        **strategy_factory.catalog(),
    }
    return (
        "// Generated from the Python strategy factory by showcase.build.\nexport const FLAVORS = "
        + json.dumps(catalog, ensure_ascii=False, indent=2)
        + ";\n"
    )


def build_site(output: Path) -> Path:
    """Copy only public assets to a fresh directory, leaving Python mode intact."""
    source_html = (STATIC / "index.html").read_text(encoding="utf-8")
    if source_html.count(ENGINE_META) != 1:
        raise ValueError("The showcase must declare one auto engine configuration.")
    source_path, output_path = STATIC.resolve(), output.resolve()
    if output_path.is_relative_to(source_path) or source_path.is_relative_to(
        output_path
    ):
        raise ValueError("Build output must be separate from the source website.")
    # A fresh destination avoids publishing unrelated files from an old build.
    shutil.copytree(STATIC, output)
    (output / "catalog.mjs").write_text(catalog_source(), encoding="utf-8")
    (output / "index.html").write_text(
        source_html.replace(ENGINE_META, ENGINE_META.replace('"auto"', '"browser"')),
        encoding="utf-8",
    )
    (output / ".nojekyll").touch()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("_site"))
    parser.add_argument(
        "--sync-catalog",
        action="store_true",
        help="refresh the local browser catalog from Python factories, then exit",
    )
    args = parser.parse_args()
    if args.sync_catalog:
        (STATIC / "catalog.mjs").write_text(catalog_source(), encoding="utf-8")
        print("Updated browser strategy catalog.")
        return
    try:
        output = build_site(args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Static website ready in {output}; publish this directory's contents.")


if __name__ == "__main__":
    main()
