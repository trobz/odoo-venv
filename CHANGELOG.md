# CHANGELOG

<!-- version list -->

## v1.10.0 (2026-03-10)

### Bug Fixes

- Normalize pkg name (hyphens/underscores) in no-build-isolation detection
  ([`290c59d`](https://github.com/trobz/odoo-venv/commit/290c59d53203b4070baba89057519b27933db8f9))

- Widen suds-jurko no-build-isolation condition to odoo_version <= '13.0'
  ([`0ce7280`](https://github.com/trobz/odoo-venv/commit/0ce7280b3db135a48f07df4a56ec97b1b5442e87))

### Features

- Auto-handle packages requiring --no-build-isolation
  ([`287d4b2`](https://github.com/trobz/odoo-venv/commit/287d4b22f964a730b7365d18938f3d363044ca62))

- Install hidden build deps before --no-build-isolation packages
  ([`65ad956`](https://github.com/trobz/odoo-venv/commit/65ad9567d48749dc5ab5f9be90fc871f0939aa5b))


## v1.9.0 (2026-03-10)

### Bug Fixes

- Only auto-ignore base req pins that actually exist in Odoo's requirements
  ([`34a69bf`](https://github.com/trobz/odoo-venv/commit/34a69bf03505fa664080af00f694d6d5123777de))

### Features

- Add google-books-api-wrapper -> idna transitive conflict
  ([`8730f85`](https://github.com/trobz/odoo-venv/commit/8730f85106e125640712f121d002e444d0fe84bb))

- Auto-ignore Odoo pins for known transitive conflicts
  ([`e94e40d`](https://github.com/trobz/odoo-venv/commit/e94e40d52e53aecc16a26a6e9951bd74e98c66aa))

- Auto-ignore Odoo's pinned requirements when user sources override them
  ([`5ac8c1f`](https://github.com/trobz/odoo-venv/commit/5ac8c1f7986258594c307159d3f6646a0fbd346a))

### Refactoring

- Extract _scan_user_sources to reduce duplication
  ([`2ce563b`](https://github.com/trobz/odoo-venv/commit/2ce563b12b0a992bd20b34880641231ae1e99341))


## v1.8.0 (2026-03-10)

### Bug Fixes

- Detect 'not found in registry' uv resolution failure
  ([`d21e3c9`](https://github.com/trobz/odoo-venv/commit/d21e3c9d0b8222dd21fa59bf4c0b21b5e7ac1d64))

- Output full uv error before skip-on-failure warning
  ([`dea1977`](https://github.com/trobz/odoo-venv/commit/dea1977cccf058c4af87967dac5e71f29698ef72))

- Prevent infinite retry loop when same package fails repeatedly
  ([`22305cb`](https://github.com/trobz/odoo-venv/commit/22305cb44be027aa066e0fd3b66ee6e0058a8a41))

### Features

- Add --skip-on-failure flag to odoo-venv create
  ([`edd1843`](https://github.com/trobz/odoo-venv/commit/edd18434494416746ea41db1a195d9972787bb21))


## v1.7.0 (2026-03-10)

### Features

- Add accept_language -> parse-accept-language; remove redundant u2flib-server hyphen key
  ([`8ab44c1`](https://github.com/trobz/odoo-venv/commit/8ab44c121b8dd28b40d8b98245060c55c2ba2f92))

- Add Asterisk -> py-Asterisk to import-to-pip mapping
  ([`566b112`](https://github.com/trobz/odoo-venv/commit/566b112d559f168cc8a2e77df69fe96f62a4fb84))

- Add dns -> dnspython to import-to-pip mapping
  ([`bfda065`](https://github.com/trobz/odoo-venv/commit/bfda065959e88efb9ffb8afdba1b3df3cd861e6e))

- Add facturx -> factur-x to import-to-pip mapping
  ([`99f90da`](https://github.com/trobz/odoo-venv/commit/99f90dab3ec6ae89e1a1f2edc1b1647c5e6d5d89))

- Add git -> GitPython mapping; lowercase all import-to-pip keys
  ([`4f97b19`](https://github.com/trobz/odoo-venv/commit/4f97b1960ca5c9c4fa15bb4b149900acb73f9878))

- Add graphql_server -> graphql-server-core to import-to-pip mapping
  ([`d5ee8ae`](https://github.com/trobz/odoo-venv/commit/d5ee8aefe3fc040acef1c176ec7a2e65ac9e23a6))

- Add MySQLdb -> MySQL-python to import-to-pip mapping
  ([`54168f3`](https://github.com/trobz/odoo-venv/commit/54168f3682ce88f014d9517f42b6ea7ab0339b99))

- Add u2flib_server / u2flib-server -> python-u2flib-server to import-to-pip mapping
  ([`823c8ef`](https://github.com/trobz/odoo-venv/commit/823c8ef5b1400ab9c420f7b1bcff32f4ecaab5f1))

- Add voicent -> Voicent-Python to import-to-pip mapping
  ([`fb04a6e`](https://github.com/trobz/odoo-venv/commit/fb04a6e5d5b0aaeda9b0756f7010a9b2b9a45c32))

- Re-add u2flib-server -> python-u2flib-server to import-to-pip mapping
  ([`973fa66`](https://github.com/trobz/odoo-venv/commit/973fa66a6e59d432735e0f59ffeecd904c312175))

- Set UV_PRERELEASE=allow on requirements install
  ([`6ecd77d`](https://github.com/trobz/odoo-venv/commit/6ecd77dbc8a7ff0706d7057909bae104b633d53a))

- Translate manifest python dep names to pip package names
  ([`fd85b29`](https://github.com/trobz/odoo-venv/commit/fd85b29b036c6b1f91a6fd95fe1b658809c83065))


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
