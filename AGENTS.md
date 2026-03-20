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

## Migration Rules

**When you modify `odoo_venv/assets/presets.toml`, you MUST also create a migration script in `odoo_venv/migrations/`.**

CI will reject PRs that change presets.toml without a new migration script.

### How migrations work

- Scripts live in `odoo_venv/migrations/` and are named `X_Y_Z.py` (e.g., `1_12_0.py` for version 1.12.0)
- The version must match or be close to the next release version in `pyproject.toml`
- On upgrade, `run_migration()` in `utils.py` runs all scripts newer than the user's last recorded version
- Each script runs as a standalone Python file (`__main__` block required)

### How to determine the version

1. Check `pyproject.toml` for the current `version`
2. Look at existing files in `odoo_venv/migrations/` to avoid collisions
3. Name your script to match the upcoming release version

### Migration patterns

**Full replacement** — use when the change affects many keys or restructures presets:

```python
from pathlib import Path


def update_presets_file():
    user_preset_path = Path("~/.local/share/odoo-venv/").expanduser() / "presets.toml"
    backup_path = user_preset_path.with_suffix(".toml.bak")
    user_preset_path.rename(backup_path)
    user_preset_path.write_text(
        (Path(__file__).parent.parent / "assets" / "presets.toml").read_text()
    )


if __name__ == "__main__":
    update_presets_file()
```

**Targeted migration** — use when only specific values change (preserves user customizations):

```python
import re
from pathlib import Path


def migrate():
    user_preset_path = Path("~/.local/share/odoo-venv/").expanduser() / "presets.toml"
    content = user_preset_path.read_text()

    # Example: add "new-package" to [ci] extra_requirement if not already present
    if "new-package" not in content:
        content = re.sub(
            r'(\[ci\].*?extra_requirement\s*=\s*")(.*?)(")',
            r'\1\2,new-package\3',
            content,
            flags=re.DOTALL,
        )

    user_preset_path.write_text(content)


if __name__ == "__main__":
    migrate()
```

Choose the pattern based on the scope of your change. When in doubt, use full replacement — it's simpler and guarantees consistency.
