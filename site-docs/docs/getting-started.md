---
icon: lucide/rocket
description: Install odoo-venv and spin up your first Odoo environment in minutes.
tags:
  - installation
  - quickstart
  - presets
---

# Getting Started

## Installation

```bash
uv tool install odoo-venv
odoo-venv --version
```

## Create an environment

```bash
odoo-venv create 19.0 --odoo-dir ~/code/odoo/19.0
```

Creates `.venv`, installs the right Python version, Odoo's `requirements.txt`, and Odoo itself in editable mode.

!!! tip "Python version is auto-selected"
    No need for `--python-version` — odoo-venv picks it based on the Odoo version.

## Presets

For recurring configurations, it is recommended to utilize presets

```bash
odoo-venv create 19.0 --odoo-dir ~/code/odoo/19.0 --preset local
```

Define presets in `~/.local/share/odoo-venv/presets.toml`. The `[common]` section applies to all presets automatically.
