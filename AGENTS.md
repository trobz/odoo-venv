# AGENTS.md

> Quick reference for AI coding agents.

## Project

- **Name**: odoo-venv
- **Description**: CLI tool to spin up isolated Odoo dev environments in seconds
- **Type**: CLI (Typer)
- **Language**: Python 3.10+
- **Package manager**: [uv](https://docs.astral.sh/uv/)
- **License**: AGPL-3.0

## Source Layout

```
odoo_venv/
├── cli/
│   ├── __init__.py
│   ├── main.py          — CLI entry point (Typer app, commands: create, create-odoo-launcher)
│   └── ovx_cmd.py       — Standalone `ovx` Typer app (delegates to ovx.py)
├── assets/              — Bundled presets.toml and launcher.sh.template
├── main.py              — Core logic: venv creation, requirement resolution, Odoo installation
├── ovx.py               — ovx orchestrator: run_ovx, build_odoo_argv, DB lifecycle
├── ovx_resolver.py      — Venv resolution and clone primitives for ovx
├── utils.py             — Preset loading/merging, config paths
├── launcher.py          — Generates ~/.local/bin/odoo-vXX launcher scripts
└── exceptions.py        — Custom exceptions (PresetNotFoundError, OdooVenvError)
```

## Key Concepts

- **Presets**: TOML-based option bundles bundled with the tool; a `[common]` section merges into all other presets by default
- **Extra commands**: Preset-defined shell commands that run at stages: `after_venv`, `after_requirements`, `after_odoo_install`; support `when` markers with `odoo_version` and PEP 508 expressions
- **Requirement filtering**: Processes Odoo's `requirements.txt`, addons dirs, and manifest `external_dependencies`; supports ignoring specific packages via comma-separated lists
- **ovx**: Standalone `ovx ADDON_PATHS` command (separate script entry point, not a subcommand of `odoo-venv`). Accepts a comma-separated list of addon paths (e.g. `ovx ./a,~/oca/b`); the first addon's manifest decides the Odoo series — mismatched modules fail at Odoo's module-not-found error; paths containing commas are not supported. Detects Odoo series from `__manifest__.py`, resolves/clones a matching venv, installs missing Python deps (union across all manifests, deduped), runs Odoo with `-i <module_a>,<module_b>`, and manages an ephemeral DB lifecycle (name joins all module names). Accepts `--addons-path` (CSV) to merge extra paths (e.g. enterprise/OCA) into the venv's stored `addons_path`; also passed to `create_odoo_venv` on fresh-venv creation. Source: `ovx.py` (orchestrator) + `ovx_resolver.py` (resolution/clone) + `cli/ovx_cmd.py` (CLI).

## Dev Commands

```
make install   # Install deps + pre-commit hooks
make check     # Lint (ruff), format, type-check (ty)
make test      # Run pytest with --doctest-modules
make build     # Build wheel
```

## Key Files

- `Makefile` — Project commands
- `pyproject.toml` — Dependencies (typer, tomli, packaging) and build config (uv_build)
- `ruff.toml` — Linter/formatter rules (line-length: 120, target: py312)
