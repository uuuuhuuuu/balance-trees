# Repository Guidelines

## Project Structure & Module Organization

This repository currently has no source code, tests, assets, or build configuration. The existing hidden directories (`.agents/`, `.codex/`, `.aws/`, and `.git/`) contain no visible project files; do not repurpose them for application code.

When adding the first implementation, organize source under `src/`, automated tests under `tests/`, and supporting documentation under `docs/`. Keep benchmarks separate from correctness tests, for example in `benchmarks/`. Document the chosen language, toolchain, and actual directory layout in `README.md`.

## Build, Test, and Development Commands

No build, test, lint, or local execution commands are configured yet. Do not assume `npm test`, `make`, or another tool is supported.

The first implementation should include reproducible setup instructions and explicit commands for building, testing, formatting, and running benchmarks. Run commands from the repository root and document required tool versions. Use `rg --files --hidden -g '!.git'` to inspect available files.

## Coding Style & Naming Conventions

No language-specific style or formatter has been established. Adopt the selected language's standard formatter and include its configuration with the initial code. Use consistent indentation, descriptive identifiers, and filenames that match the language's conventions. Keep tree operations and invariant checks small and focused; explain non-obvious balancing rules in comments.

## Testing Guidelines

No testing framework or coverage threshold is configured. Add automated tests alongside each implementation change. For balanced-tree implementations, cover empty trees, duplicate-key behavior, insertion, deletion, lookup, and structural invariants after mutations. Use deterministic seeds for randomized tests and include regression cases for fixed defects. Choose test names that describe the operation and expected behavior.

## Commit & Pull Request Guidelines

Git history is unavailable in this checkout, so no existing commit convention can be inferred. Use concise, imperative commit subjects such as `Add insertion invariant tests`.

Pull requests should describe the problem, implementation, and validation commands with results. Link related issues when available. For algorithm or performance changes, explain complexity tradeoffs and provide reproducible benchmark inputs when claiming improvements.
