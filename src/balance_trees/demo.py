"""Print a small tree and insertion measurements, optionally after every step."""

import argparse
from pathlib import Path

from .flavors import TreeFlavor
from .graphviz import render_graphviz, write_dot
from .rendering import render_tree
from .reporting import text_table
from .strategies import STRATEGIES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", choices=STRATEGIES, default="halving")
    parser.add_argument("--keys", type=int, nargs="+", default=list(range(1, 16)))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--max-nodes", type=int, default=100)
    parser.add_argument("--dot", type=Path, help="export the final tree as DOT")
    parser.add_argument(
        "--graph", type=Path, help="render the final tree as SVG, PNG or PDF"
    )
    parser.add_argument(
        "--show-nulls",
        action="store_true",
        help="draw missing children in Graphviz output",
    )
    parser.add_argument(
        "--highlight-key", type=int, help="highlight a key in Graphviz output"
    )
    args = parser.parse_args()
    if args.max_depth < 0 or args.max_nodes < 1:
        parser.error("max-depth must be nonnegative and max-nodes positive")
    if args.graph is not None and args.graph.suffix.lower() not in {
        ".svg",
        ".png",
        ".pdf",
    }:
        parser.error("--graph requires a .svg, .png or .pdf suffix")
    if (
        args.dot is not None
        and args.graph is not None
        and args.dot.resolve() == args.graph.resolve()
    ):
        parser.error("--dot and --graph must name different files")
    tree = TreeFlavor(STRATEGIES[args.strategy](), seed=args.seed)
    rows = []
    print(f"Flavor: {args.strategy} | Seed: {args.seed}")
    for step, key in enumerate(args.keys, start=1):
        stats = tree.insert(key)
        rows.append(
            [
                str(step),
                str(key),
                "yes" if stats.inserted else "no",
                str(stats.insertion_depth),
                str(stats.rotations),
                str(stats.visits),
                str(stats.random_bits),
            ]
        )
        if args.trace:
            print(
                f"\nStep {step}: insert {key} | rotations={stats.rotations}, visits={stats.visits}, bits={stats.random_bits}"
            )
            print(
                render_tree(
                    tree.tree,
                    max_depth=args.max_depth,
                    max_nodes=args.max_nodes,
                    ascii_only=args.ascii,
                )
            )
    print()
    print(
        text_table(
            ["Step", "Key", "Inserted", "Depth", "Rotations", "Visits", "Bits"], rows
        )
    )
    print("\nFinal tree:")
    print(
        render_tree(
            tree.tree,
            max_depth=args.max_depth,
            max_nodes=args.max_nodes,
            ascii_only=args.ascii,
        )
    )
    depths = tree.tree.depths()
    print(
        f"\nNodes: {len(depths)} | Height: {max(depths.values())} | Mean depth: {sum(depths.values()) / len(depths):.2f}"
    )
    options = {
        "title": f"{args.strategy} | seed={args.seed} | n={len(depths)}",
        "show_nulls": args.show_nulls,
        "highlight_key": args.highlight_key,
    }
    try:
        if args.dot is not None:
            print(f"DOT written to {write_dot(tree.tree, args.dot, **options)}")
        if args.graph is not None:
            print(
                f"Graph written to {render_graphviz(tree.tree, args.graph, **options)}"
            )
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
