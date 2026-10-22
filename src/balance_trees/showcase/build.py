"""Prepare a browser-only static website for GitHub Pages or another host."""

import argparse
import shutil
from pathlib import Path

from .server import STATIC

ENGINE_META = '<meta name="rotation-lab-engine" content="auto">'


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
    (output / "index.html").write_text(
        source_html.replace(ENGINE_META, ENGINE_META.replace('"auto"', '"browser"')),
        encoding="utf-8",
    )
    (output / ".nojekyll").touch()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("_site"))
    args = parser.parse_args()
    try:
        output = build_site(args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Static website ready in {output}; publish this directory's contents.")


if __name__ == "__main__":
    main()
