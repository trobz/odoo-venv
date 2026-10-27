# odoo-venv

A command-line tool to spin up isolated Odoo dev environments in seconds.

```bash
uv tool install odoo-venv
```

**Documentation:** <https://trobz.github.io/odoo-venv>

## Contributing

### Setup

```bash
make install
```

Creates the project's `uv` virtual environment and installs the pre-commit hooks.

### Checks

```bash
make check
make test
```

`make check` verifies `uv.lock` is consistent with `pyproject.toml`, runs pre-commit
(ruff check + ruff format), and type-checks with `ty`. `make test` runs pytest with
`--doctest-modules`, so docstring examples under `odoo_venv/` execute as tests.

To test against a clean cache (no previously resolved packages):

```bash
uv cache clean --force
```

### Documentation

```bash
make docs-serve   # preview locally
make docs         # build
```

Sources live under `site-docs/docs/`, configured by `zensical.toml`. `site/` is
generated output and is gitignored — never edit it directly. Docs deploy
automatically on push to `main` when `site-docs/**` or `zensical.toml` changes.

### Commit messages

Conventional Commits are **required**. `python-semantic-release` derives the next
version and `CHANGELOG.md` from commit types on every push to `main`.

### Releases

Releases are automatic on merge to `main` — do not hand-edit `version` in
`pyproject.toml` or `CHANGELOG.md`.
