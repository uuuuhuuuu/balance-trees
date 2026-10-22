"""Deterministic DOT export and optional rendering through Graphviz's dot CLI."""

import json
import shutil
import subprocess
from collections import deque
from pathlib import Path

from .tree import BST


def to_dot(
    tree: BST,
    *,
    title: str = "Binary search tree",
    show_nulls: bool = False,
    highlight_key: int | None = None,
) -> str:
    """Export the entire tree without requiring Graphviz or changing the tree.

    IDs follow breadth-first traversal, so equal trees produce equal DOT.
    Invisible null children preserve left/right placement when only one exists.
    With show_nulls, every missing child is drawn explicitly instead.
    """
    tree.depths()  # Reject cycles, ordering violations and broken parent links.
    lines = [
        "digraph BST {",
        "  graph [rankdir=TB, ordering=out, bgcolor=white, pad=0.3,",
        '         nodesep=0.3, ranksep=0.5, fontname="DejaVu Sans", labelloc=t,',
        f"         label={json.dumps(title, ensure_ascii=False)}];",
        '  node [shape=circle, style=filled, fillcolor="#eef2ff",',
        '        color="#6366f1", fontname="DejaVu Sans", fontsize=12];',
        '  edge [color="#64748b", fontcolor="#475569",',
        '        fontname="DejaVu Sans", fontsize=9, arrowsize=0.6];',
    ]
    if tree.root is None:
        lines.append('  empty [label="<empty>", shape=plaintext];')
    queue = deque([(tree.root, 0)]) if tree.root is not None else deque()
    next_id = 1
    while queue:
        node, node_id = queue.popleft()
        highlight = (
            ', fillcolor="#fde68a", color="#d97706"'
            if node.key == highlight_key
            else ""
        )
        lines.append(f'  n{node_id} [label="{node.key}"{highlight}];')
        leaf = node.left is None and node.right is None
        for side, child in (("L", node.left), ("R", node.right)):
            if child is not None:
                child_id = next_id
                next_id += 1
                lines.append(f'  n{node_id} -> n{child_id} [label="{side}"];')
                queue.append((child, child_id))
            elif show_nulls or not leaf:
                null_id = f"null_{node_id}_{side}"
                if show_nulls:
                    lines.append(
                        f'  {null_id} [label="∅", shape=plaintext, fontcolor="#94a3b8"];'
                    )
                    lines.append(
                        f'  n{node_id} -> {null_id} [label="{side}", style=dashed, color="#cbd5e1"];'
                    )
                else:
                    lines.append(f'  {null_id} [label="", shape=point, style=invis];')
                    lines.append(f"  n{node_id} -> {null_id} [style=invis];")
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_dot(
    tree: BST,
    path: str | Path,
    *,
    title: str = "Binary search tree",
    show_nulls: bool = False,
    highlight_key: int | None = None,
) -> Path:
    """Write portable DOT source; Graphviz does not need to be installed."""
    source = to_dot(
        tree, title=title, show_nulls=show_nulls, highlight_key=highlight_key
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source, encoding="utf-8")
    return destination


def render_graphviz(
    tree: BST,
    path: str | Path,
    *,
    title: str = "Binary search tree",
    show_nulls: bool = False,
    highlight_key: int | None = None,
    timeout: float = 30.0,
) -> Path:
    """Render SVG, PNG or PDF; infer the output format from the file suffix.

    No Python Graphviz dependency is needed. The system dot executable must
    be on PATH. Rendering finishes before the destination file is written.
    """
    destination = Path(path)
    output_format = destination.suffix.lower().removeprefix(".")
    if output_format not in {"svg", "png", "pdf"}:
        raise ValueError("Graphviz output must have a .svg, .png or .pdf suffix")
    executable = shutil.which("dot")
    if executable is None:
        raise RuntimeError(
            "Graphviz 'dot' was not found on PATH. Install Graphviz, "
            "or export DOT with write_dot / --dot instead."
        )
    source = to_dot(
        tree, title=title, show_nulls=show_nulls, highlight_key=highlight_key
    )
    try:
        result = subprocess.run(
            [executable, f"-T{output_format}"],
            input=source.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Graphviz rendering failed: {detail}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"Graphviz rendering exceeded {timeout:g} seconds"
        ) from error
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(result.stdout)
    return destination
