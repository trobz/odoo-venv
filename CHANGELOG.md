# CHANGELOG

<!-- version list -->

## v1.6.2 (2026-03-10)

### Bug Fixes

- **cli**: Fix --preset being ignored when --project-dir precedes it in argv
  ([`b235d56`](https://github.com/trobz/odoo-venv/commit/b235d566b9af0b74089ebd1664606808c0243ece))

- **cli**: Make --extra-requirement additive to preset value
  ([`ffa423a`](https://github.com/trobz/odoo-venv/commit/ffa423ac3bae4cbd25de412510a454d954f2abc6))


## v1.6.1 (2026-03-10)

### Bug Fixes

- Don't filter extra_requirements through ignore list
  ([`f03cae0`](https://github.com/trobz/odoo-venv/commit/f03cae0d6e7d37127d5239b514777593ee1e3407))

- **presets**: Bump urllib3 pin from 1.26.5 to 1.26.14 in common preset
  ([`0ba671a`](https://github.com/trobz/odoo-venv/commit/0ba671a5acd57525b792930bae24a088f9af897c))


## v1.6.0 (2026-03-09)

### Features

- Add compare command to diff package versions across venvs
  ([`79c793d`](https://github.com/trobz/odoo-venv/commit/79c793da980daa86af45cd4d5bf6cfce5c8c01f4))


## v1.5.0 (2026-03-09)

### Features

- Add --report-errors flag to create command
  ([`40a5303`](https://github.com/trobz/odoo-venv/commit/40a5303988d280fc176e9aa5ac11f46ba00b4eb2))


## v1.4.0 (2026-03-03)

### Bug Fixes

- **ci**: Pre-install uv in e2e workflow with caching
  ([`71b4006`](https://github.com/trobz/odoo-venv/commit/71b400645d0757215ef0828c215e8fe014119979))

### Features

- Support escaped commas in --extra-requirement
  ([`d22bade`](https://github.com/trobz/odoo-venv/commit/d22bade81549b610d6415e19a969bd48b79a5ead))


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
