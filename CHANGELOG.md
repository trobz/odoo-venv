# CHANGELOG

<!-- version list -->

## v1.20.0 (2026-04-20)

### Features

- Add list command to discover and display Odoo venvs
  ([`9896ba7`](https://github.com/trobz/odoo-venv/commit/9896ba7b13247b85e91685853dc95851f39e0165))


## v1.19.0 (2026-04-20)

### Features

- Add show command
  ([`748dc34`](https://github.com/trobz/odoo-venv/commit/748dc3452cd50bc2a4fff901cde2a76df1edb1ed))


## v1.18.0 (2026-04-14)

### Bug Fixes

- **ci**: Exclude test fixtures from ty type checking
  ([`1509185`](https://github.com/trobz/odoo-venv/commit/15091859aad16058cbeb6275afc105d989f433d8))

- **test**: Exclude fixtures and worktrees from pytest collection
  ([`bd46553`](https://github.com/trobz/odoo-venv/commit/bd46553ae14eb77c561889e74629cad054363b7c))

### Features

- Add automated tests for action.yml
  ([`3a1c501`](https://github.com/trobz/odoo-venv/commit/3a1c501cce8fc3542ea589f741b03d9a578f9b03))

- Add composite github action
  ([`df2c6b6`](https://github.com/trobz/odoo-venv/commit/df2c6b6c826ac9aff707ad8720b25a69cf22d078))


## v1.17.0 (2026-04-08)

### Features

- **cli**: Add `activate` command to spawn shell with venv activated
  ([`e42c0c9`](https://github.com/trobz/odoo-venv/commit/e42c0c9e6573c1db196acc3dd667f1864dfed2bf))

- **presets**: Add click-odoo-contrib dependency to all presets
  ([`eb50aae`](https://github.com/trobz/odoo-venv/commit/eb50aae5c01033ce92e2fc937eed686bb7b7e71d))


## v1.16.1 (2026-04-02)

### Bug Fixes

- **update**: Have option to skip confirmation
  ([`9defa6d`](https://github.com/trobz/odoo-venv/commit/9defa6d1f3ea127ecb82c8899e6d7f0ade71c5b0))


## v1.16.0 (2026-04-01)

### Bug Fixes

- Write default preset to .odoo-venv.toml
  ([`b365dff`](https://github.com/trobz/odoo-venv/commit/b365dffc3be40b0a2e0187b7d65c5ba142f590dc))

### Features

- Add update command and venv configuration management
  ([`b9b9679`](https://github.com/trobz/odoo-venv/commit/b9b967944f8f473312b4425131cec7d9e93f7837))

- **create**: Persist CLI args to .odoo-venv.toml after venv creation
  ([`bf2558a`](https://github.com/trobz/odoo-venv/commit/bf2558a81e1c3994e602f7bdc3ade89372dd9254))

### Refactoring

- **create**: Extract _build_extra_requirements helper
  ([`86fd2fd`](https://github.com/trobz/odoo-venv/commit/86fd2fdd54da07241c1d130de9d7d9f80cf4df98))


## v1.15.1 (2026-03-31)

### Bug Fixes

- **presets**: Apply common preset in eager callback so default_map works
  ([`1af49ce`](https://github.com/trobz/odoo-venv/commit/1af49cec2e5a5f71cb7bf4e32cc23297e1c4d733))


## v1.15.0 (2026-03-26)

### Bug Fixes

- **cli**: Add version mismatch detection between --project-dir and --odoo-dir
  ([`7789cb5`](https://github.com/trobz/odoo-venv/commit/7789cb5cd60ae3ba20904ad14e24c74111fe4fac))

### Documentation

- Update documentation for opinionated-presets
  ([`68b9fed`](https://github.com/trobz/odoo-venv/commit/68b9fedb29e4a6624d7405545492a2e7d2a36f39))

### Features

- **cli**: Remove odoo_version positional argument, infer from --odoo-dir
  ([`036a8c2`](https://github.com/trobz/odoo-venv/commit/036a8c298b66891ca14ade6d955ef29d9223684c))

- **presets**: Apply common preset by default when no --preset given
  ([`9b19fce`](https://github.com/trobz/odoo-venv/commit/9b19fcec639c1e07987ac1cf6648dd931f65fbe4))

### Refactoring

- **presets**: Remove migration system and user-customizable presets
  ([`d85c18f`](https://github.com/trobz/odoo-venv/commit/d85c18f9785b53c6d1f383a947a93e431c6737ee))


## v1.14.1 (2026-03-26)

### Bug Fixes

- **presets**: Pin psycopg2 to 2.8.3 for Odoo 12 on Python < 3.8
  ([`57f3310`](https://github.com/trobz/odoo-venv/commit/57f3310a10442c9a4b844942e05ae0e2b346b723))


## v1.14.0 (2026-03-26)

### Features

- **create**: Add --force option to recreate virtual environment
  ([`b3a3ff2`](https://github.com/trobz/odoo-venv/commit/b3a3ff288aa94f6051b7068ee15c4597bc4f83c6))


## v1.13.1 (2026-03-26)

### Bug Fixes

- **ci**: Pass codebase arg to odoo-addons-path in OCA e2e jobs
  ([`969362d`](https://github.com/trobz/odoo-venv/commit/969362d01279807cc1b22e212e7f22926e921368))

- **launcher**: Bypass broken shebang by invoking bin/odoo through python
  ([`5bb13cd`](https://github.com/trobz/odoo-venv/commit/5bb13cd20a1b9e3281c58182610e2ddff1daf4df))

- **launcher**: Resolve real major version for non-numeric branches like master
  ([`d4f6099`](https://github.com/trobz/odoo-venv/commit/d4f6099d50a86b72fa3de108ebf1d72128db041a))


## v1.13.0 (2026-03-24)

### Features

- **e2e**: Add launcher smoke test to catch runtime dependency errors
  ([`8147c30`](https://github.com/trobz/odoo-venv/commit/8147c30d9dc025b4536d59d707019bb621193301))


## v1.12.0 (2026-03-19)

### Features

- **docs**: Add documentation site with landing page, getting started guide, and troubleshooting
  sections
  ([`e438a48`](https://github.com/trobz/odoo-venv/commit/e438a485adfb48c8ce4a09786a3b6185f924189c))


## v1.11.2 (2026-03-19)

### Bug Fixes

- **presets**: Pin setuptools<82.0 for Python 3.10 on Odoo 18.0+
  ([`9fa32b5`](https://github.com/trobz/odoo-venv/commit/9fa32b5e6ac2c7cf61b055a5296c9df1fc4691ba))


## v1.11.1 (2026-03-16)

### Bug Fixes

- **compare**: Normalize package names per PEP 503 for consistent matching
  ([`03fe28c`](https://github.com/trobz/odoo-venv/commit/03fe28caf8460f39d88d81439d0d8df98b15706b))


## v1.11.0 (2026-03-13)

### Features

- Accept requirements files as compare sources
  ([`deb8232`](https://github.com/trobz/odoo-venv/commit/deb82320c5bc88e748de4d657c7a8840cade14ff))

- Support remote venvs in compare command via SSH
  ([`73cf17a`](https://github.com/trobz/odoo-venv/commit/73cf17a071a85f7ae7aa81683f336dee2e19dc37))


## v1.10.1 (2026-03-12)

### Bug Fixes

- Handle magento as NBI package so transitive suds-jurko build uses legacy setuptools
  ([`fbb7b44`](https://github.com/trobz/odoo-venv/commit/fbb7b444600a2e3f328f38bc8eae980a78b6db2b))

- Map MySQLdb to mysqlclient and drop mysql-python NBI workaround
  ([`ec81f10`](https://github.com/trobz/odoo-venv/commit/ec81f10f60de160377e9821de08d7ec9ff971850))

- Relax python-dateutil and pytz pins when altair is required
  ([`7c7fb14`](https://github.com/trobz/odoo-venv/commit/7c7fb148f94c8b400b763c7cf60582bca441849b))

- Relax python-dateutil and pytz pins when pandas is required
  ([`ed8b409`](https://github.com/trobz/odoo-venv/commit/ed8b4095211974f04a400a4a67fb3231a1bb20ea))

- Relax requests pin when klaviyo-api is required by an addon
  ([`03c0285`](https://github.com/trobz/odoo-venv/commit/03c0285142ff1474fd2d81bb7e3d5313d2ec9191))


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
