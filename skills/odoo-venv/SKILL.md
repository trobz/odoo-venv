---
name: odoo-venv
description: Create and manage Odoo Python virtual environments and launcher scripts using odoo-venv CLI (no install needed). Use when setting up Odoo dev environment, creating venv, generating launcher script, or running Odoo locally. Handles Python version selection, addon paths, dependency installation, launcher generation. Presets include local (dev), demo, project, ci (testing).
---

## Arguments

- `{VERSION}`: Odoo version (e.g., `17.0`, `18.0`)
- `local`: Development preset (debugpy, ipython, coverage)
- `ci`: CI/Testing preset (coverage, pylint, websocket-client)
- `project`: Minimal preset (uses ./requirements.txt)

# Odoo Venv

Create isolated Odoo development environments and launcher scripts (no pip install needed).

## Quick Start

> **Path defaults:** `~/code/odoo/odoo/{VERSION}` for Odoo source, `~/code/venvs/{VERSION}` for venvs.
> These match `tlc` config defaults. Override with `--odoo-dir` and `--venv-dir`.

```bash
# Create venv for Odoo 17.0 with local preset (development)
odoo-venv create 17.0 \
    --venv-dir ~/code/venvs/17.0 \
    --odoo-dir ~/code/odoo/odoo/17.0 \
    --addons-path ~/code/odoo/addons/web,~/code/odoo/addons/mail \
    --preset local
```

## Standard Project Layout

```
~/code/odoo/
├── odoo/
│   ├── 14.0/    # Odoo source code
│   ├── 16.0/
│   ├── 17.0/
│   └── 18.0/
└── addons/      # Custom addons directories
    ├── web/
    ├── mail/
    └── project-name/
```

## Create Venv Commands

### With Preset (Recommended)

```bash
# Development - includes debugpy, ipython, coverage, pylint-odoo
odoo-venv create {VERSION} --venv-dir ~/code/venvs/{VERSION} \
    --odoo-dir ~/code/odoo/odoo/{VERSION} --addons-path {ADDONS_PATH} --preset local

# CI/Testing - includes coverage, pylint, websocket-client
odoo-venv create {VERSION} --venv-dir ~/code/venvs/{VERSION} \
    --odoo-dir ~/code/odoo/odoo/{VERSION} --addons-path {ADDONS_PATH} --preset ci

# Project - minimal deps, uses ./requirements.txt
odoo-venv create {VERSION} --venv-dir ~/code/venvs/{VERSION} \
    --odoo-dir ~/code/odoo/odoo/{VERSION} --addons-path {ADDONS_PATH} --preset project
```

### Without Preset

```bash
odoo-venv create {VERSION} \
    --venv-dir ~/code/venvs/{VERSION} \
    --odoo-dir ~/code/odoo/odoo/{VERSION} \
    --addons-path {ADDONS_PATH} \
    --install-addons-dirs-requirements \
    --extra-requirement "debugpy,ipython"
```

## Launcher Generation

### A. Create venv + launcher together

```bash
odoo-venv create {VERSION} \
    --odoo-dir ~/code/odoo/odoo/{VERSION} \
    --venv-dir ~/code/venvs/{VERSION} \
    --preset local \
    --create-launcher
```

Result: venv at `~/code/venvs/{VERSION}/` + launcher at `~/.local/bin/odoo-v{major}`

### B. Generate launcher for existing venv

```bash
odoo-venv create-odoo-launcher {VERSION} \
    --venv-dir ~/code/venvs/{VERSION}
```

## Smart Launcher Flow

Decision tree when launcher is needed:

1. **Check launcher:** `test -x ~/.local/bin/odoo-v{major}`
   - If exists → done, use it
2. **Check venv:** `test -d ~/code/venvs/{VERSION}/bin/activate`
   - If exists → run `create-odoo-launcher` (approach B)
   - If not → run full `create` with `--create-launcher` (approach A)
3. **Verify PATH:** `echo $PATH | grep -q "$HOME/.local/bin"`
   - If not in PATH → `export PATH="$HOME/.local/bin:$PATH"`

## Workflow: When User Asks to Create Venv

1. Ask for Odoo version if not specified
2. Ask for addons path if not specified (or use `odoo-addons-path`)
3. Suggest preset based on context:
   - Development work → `local`
   - Running tests → `ci`
   - Production/staging → `project`
4. Run `odoo-venv create` with `--venv-dir ~/code/venvs/{VERSION}`
5. Generate launcher with `--create-launcher` or separate `create-odoo-launcher`

## Verify Installation

```bash
# Check launcher works
odoo-v18 --version

# Or activate venv manually
source ~/code/venvs/{VERSION}/bin/activate
odoo --version
```

## References

- [Presets Configuration](references/presets.md) - Available presets and their options
- [GitHub Repository](https://github.com/trobz/odoo-venv)

## Cross-References

- **`tlc` skill** — Bulk venv creation via `create-venvs` command
- **`odoo-run` skill** — Using the generated launcher to run Odoo
