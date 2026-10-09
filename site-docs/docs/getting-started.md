---
icon: lucide/rocket
description: Install odoo-venv and spin up your first Odoo environment in minutes.
tags:
  - installation
  - quickstart
  - presets
  - ovx
---

# Getting Started

## Installation

```bash
uv tool install odoo-venv
odoo-venv --version
```

## Create an environment

```bash
odoo-venv create --odoo-dir ~/code/odoo/19.0
```

Creates `.venv`, installs the right Python version, Odoo's `requirements.txt`, and Odoo itself in editable mode. The Odoo version is inferred automatically from the source directory.

!!! tip "Python version is auto-selected"
    No need for `--python-version` — odoo-venv picks it based on the Odoo version.

## Presets

For recurring configurations, it is recommended to utilize presets

```bash
odoo-venv create --odoo-dir ~/code/odoo/19.0 --preset local
```

The `[common]` section applies to all presets automatically. Built-in presets are: local, demo, project, ci.

## Run an addon on-the-fly

For a one-off run against an addon without a project of its own, `ovx` skips the
project scaffolding entirely:

```bash
ovx ./crm_eav_fields --odoo-dir ~/code/odoo/19.0 --venv-dir ~/code/venvs/19.0
```

The first run at a given `--venv-dir` prompts to build a permanent venv there (default
yes); later runs reuse it. In CI, with no interactive terminal, `ovx` refuses to build
unattended — pre-build the venv first with `odoo-venv create --venv-dir <dir> --odoo-dir
<odoo source>`.

See the [`ovx` reference](reference/page-4.md) for the full option list, clone
behaviour, and series resolution rules.
