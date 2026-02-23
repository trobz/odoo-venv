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
│   └── main.py          — CLI entry point (Typer app, commands: create, create-odoo-launcher)
├── assets/              — Bundled presets.toml and launcher.sh.template
├── migrations/          — Version migration scripts (e.g., 1_0_0.py)
├── main.py              — Core logic: venv creation, requirement resolution, Odoo installation
├── utils.py             — Preset loading/merging, migration runner, config paths
├── launcher.py          — Generates ~/.local/bin/odoo-vXX launcher scripts
└── exceptions.py        — Custom exceptions (PresetNotFoundError)
```

## Key Concepts

- **Presets**: TOML-based option bundles stored at `~/.local/share/odoo-venv/presets.toml`; a `[common]` section merges into all other presets
- **Extra commands**: Preset-defined shell commands that run at stages: `after_venv`, `after_requirements`, `after_odoo_install`; support `when` markers with `odoo_version` and PEP 508 expressions
- **Requirement filtering**: Processes Odoo's `requirements.txt`, addons dirs, and manifest `external_dependencies`; supports ignoring specific packages via comma-separated lists

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
