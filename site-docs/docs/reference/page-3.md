---
icon: lucide/rocket
description: "odoo-venv create-odoo-launcher — generate a launcher script in ~/.local/bin/ for the Odoo environment."
tags:
  - cli
  - reference
  - launcher
---

# `odoo-venv create-odoo-launcher`

Generate a launcher script in `~/.local/bin/` for the Odoo environment.

```bash
odoo-venv create-odoo-launcher ODOO_VERSION [OPTIONS]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `ODOO_VERSION` | Yes | Odoo version, e.g. `19.0`. |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--venv-dir` | — | Path to the virtual environment. |
| `--force` | `False` | Overwrite existing launcher script. |

## Example

```bash
odoo-venv create-odoo-launcher 19.0 --venv-dir ./.venv --force
```

Creates `~/.local/bin/odoo-v19` that activates the venv and runs Odoo.
