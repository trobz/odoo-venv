# AGENTS.md

> CLI tool to spin up isolated Odoo dev environments (`odoo-venv`, `ovx`).

## Commands

```
make install   # Install deps + pre-commit hooks
make check     # Lint (ruff), format, type-check (ty)
make test      # Run pytest with --doctest-modules
make build     # Build wheel
make docs      # Build documentation site
```

## Rules

- Use `uv` / `make`, never `pip` or a bare `python -m venv` — `make check` runs `uv lock --locked` and fails on drift (`Makefile:8-11`, `pyproject.toml:34-36`).
- Commit messages must be Conventional Commits — `python-semantic-release` derives the version and changelog from commit types; a non-conforming message silently produces no release (`.github/workflows/release.yaml:34-41`, `CHANGELOG.md`).
- Never hand-edit `version` in `pyproject.toml` or `CHANGELOG.md` — release automation overwrites it, or the tag and the file disagree (`.github/workflows/release.yaml:34-41`, `pyproject.toml:3`).
- Never edit files under `site/` — it is generated (`zensical.toml:7`) and gitignored (`.gitignore:168`); the next `make docs` / docs deploy overwrites it and nothing is committed (`.github/workflows/docs.yaml:34`). Docs sources live in `site-docs/docs/`; config is `zensical.toml`.
- `tests/fixtures/addon-failing-test` and `addon-bad-import` fail **on purpose** — do not "fix" them. They assert the GitHub Action correctly fails on a broken test / bad import (`.github/workflows/test-action-addon-tests-failing.yml`, `test-action-addon-install-failing.yml`); repairing them silently disables that failure-path coverage.

## Definition of done

`make check && make test` both pass (`Makefile:8-20`, `.github/workflows/pre-commit.yaml`, `.github/workflows/test.yaml`).
