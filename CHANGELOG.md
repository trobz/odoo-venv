# CHANGELOG

<!-- version list -->

## v1.3.0 (2026-02-26)

### Bug Fixes

- Extract project-dir detection into helpers to fix potential NameError
  ([`4184ac7`](https://github.com/trobz/odoo-venv/commit/4184ac72c8764e3462241a53e830e07712aa84e3))

### Features

- Add --project-dir to auto-detect addons path, odoo dir, and version
  ([`ea1e465`](https://github.com/trobz/odoo-venv/commit/ea1e465725c45065f17ac08559d08a999809c008))

- Utilize public API of odoo-addons-path
  ([`5a4cb9f`](https://github.com/trobz/odoo-venv/commit/5a4cb9fa5392579db128697ea1e28f2f28dd8106))


## v1.2.0 (2026-02-12)

### Bug Fixes

- Scope gevent override to linux in common preset
  ([`32d1e0e`](https://github.com/trobz/odoo-venv/commit/32d1e0ee91830e97a2a32c13193c065eba244801))

- **presets**: Pin setuptools below pkg_resources removal
  ([`3b71e7e`](https://github.com/trobz/odoo-venv/commit/3b71e7eb63701fb263600b81533104602dfcde41))

### Features

- Add Odoo launcher script generation
  ([`d7a2892`](https://github.com/trobz/odoo-venv/commit/d7a2892545f6e6809a95bedf143dc129b21c7cf3))


## v1.1.0 (2026-02-09)

### Documentation

- Add clean-state tips for developers
  ([`8f0bf75`](https://github.com/trobz/odoo-venv/commit/8f0bf750ccb2bad0c1fbb70b8ac17cc9c9d9b518))

### Features

- Add extra_commands support to presets with odoo_version markers
  ([`5432ae3`](https://github.com/trobz/odoo-venv/commit/5432ae3a47176a1aab632848813af19a9aeaac5b))

- **cli**: Add -V/--version flag to display version
  ([`b3d9ffe`](https://github.com/trobz/odoo-venv/commit/b3d9ffe2954e89dafccad6c46de74fb611f9c88b))


## v1.0.2 (2026-02-02)

### Bug Fixes

- **cli**: Prevent Typer from collapsing 'create' command
  ([`74b9994`](https://github.com/trobz/odoo-venv/commit/74b99945aefb5e0e59e092f6f27ea62f12b049bc))


## v1.0.1 (2026-01-19)

### Bug Fixes

- We need transitive dependencies installed as well (e.g. zeep->cached-property)
  ([`fc97073`](https://github.com/trobz/odoo-venv/commit/fc9707394c35b23d7b1ab93ffc4dca18dabdf148))


## v1.0.0 (2025-12-03)

- Initial Release
