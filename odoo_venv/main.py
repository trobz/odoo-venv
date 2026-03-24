import ast
import operator
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import typer
from packaging.markers import Marker, default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import parse as parse_version


class ReqSource(Enum):
    """Where a requirement came from — determines priority during conflict resolution.

    BASE: Odoo's own requirements.txt (lowest priority in conflicts)
    ADDON: OCA addons dir requirements.txt or manifest external_dependencies
    PRESET: User's extra_requirement / extra_requirements_file (highest priority)
    """

    BASE = "base"
    ADDON = "addon"
    PRESET = "preset"


@dataclass
class TaggedRequirement:
    """A requirement line paired with its source type and origin file.

    Attributes:
        raw_line: The original requirement string (e.g. "python-stdnum==1.8")
        requirement: Parsed Requirement object, or None if line couldn't be parsed
        source: Which category this requirement came from
        origin: Human-readable origin (e.g. "odoo/requirements.txt", "web/__manifest__.py")
    """

    raw_line: str
    requirement: Requirement | None
    source: ReqSource
    origin: str


PKG_NAME_PATTERN = re.compile(r"(?P<lib_name>[a-z0-9A-Z\-\_\.]+)((>|<|=)=)?(.*)")


def _normalize_pkg_name(line: str) -> str:
    """Extract and normalise a package name from a requirement line.

    >>> _normalize_pkg_name("python-ldap>=3.0")
    'python-ldap'
    >>> _normalize_pkg_name("PyYAML")
    'pyyaml'
    """
    match = PKG_NAME_PATTERN.match(line.strip())
    name = match.group("lib_name") if match else line.strip()
    return re.sub(r"[-_.]", "-", name.lower())


VALID_STAGES = {"after_venv", "after_requirements", "after_odoo_install"}

# In Odoo <= 12.0, external_dependencies.python lists importable module names, not pip package
# names (the module loader used importlib.import_module to validate them).  This mapping translates
# the most common mismatches so we can install the correct pip package.
# See: https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/models/ir_module.py#L316-L331
#
# Starting from 13.0 modules should list pip package names, but many (especially OCA ports)
# still use import names in practice, so the mapping is applied unconditionally.
_MANIFEST_IMPORT_TO_PIP: dict[str, str] = {
    "stdnum": "python-stdnum",
    "crypto": "pycryptodome",
    "openssl": "pyOpenSSL",
    "dateutil": "python-dateutil",
    "yaml": "pyyaml",
    "usb": "pyusb",
    "serial": "pyserial",
    "pil": "Pillow",
    "magic": "python-magic",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "ldap": "python-ldap",
    "voicent": "Voicent-Python",
    "asterisk": "py-Asterisk",
    "facturx": "factur-x",
    "mysqldb": "mysqlclient",
    "u2flib_server": "python-u2flib-server",
    "u2flib-server": "python-u2flib-server",
    "git": "GitPython",
    "accept_language": "parse-accept-language",
    "dns": "dnspython",
    "graphql_server": "graphql-server-core",
}

_COMPARISON_OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


def _evaluate_marker(
    marker_expr: str,
    odoo_version: str,
    python_version: str | None,
) -> bool:
    """Evaluate a marker expression, supporting custom variable ``odoo_version``.

    For pure PEP 508 expressions, delegates to ``packaging.markers.Marker``.
    For expressions containing ``odoo_version``, uses a lightweight custom
    evaluator that supports version comparisons and boolean ``and``/``or``.

    Note: if *python_version* is None, marker evaluation uses the system
    Python version from ``packaging.markers.default_environment()``.
    """
    if not marker_expr:
        return True

    env: dict[str, str] = {**default_environment()}
    if python_version:
        env["python_version"] = ".".join(python_version.split(".")[:2])
        env["python_full_version"] = python_version

    if "odoo_version" not in marker_expr:
        try:
            return Marker(marker_expr).evaluate(environment=env)
        except Exception:
            return False

    env["odoo_version"] = odoo_version
    return _evaluate_version_expr(marker_expr, env)


def _evaluate_version_expr(marker_expr: str, variables: dict[str, str]) -> bool:
    """Evaluate a marker expression with version comparisons.

    Handles ``or`` (lower precedence) and ``and`` (higher precedence) boolean
    operators, and ``<``, ``<=``, ``>``, ``>=``, ``==``, ``!=`` on version-like
    values looked up from *variables*.
    """
    expr = marker_expr.strip()

    # Split on 'or' first (lower precedence = outermost split)
    if " or " in expr:
        return any(_evaluate_version_expr(p.strip(), variables) for p in expr.split(" or "))

    if " and " in expr:
        return all(_evaluate_version_expr(p.strip(), variables) for p in expr.split(" and "))

    # Parse: variable OP 'value'
    match = re.match(r"(\w+)\s*(<=|>=|<|>|==|!=)\s*['\"]([^'\"]+)['\"]", expr)
    if not match:
        return False

    var_name, op_str, compare_value = match.groups()
    actual_value = variables.get(var_name)
    if actual_value is None:
        return False

    try:
        return _COMPARISON_OPS[op_str](parse_version(actual_value), parse_version(compare_value))
    except Exception:
        return _COMPARISON_OPS[op_str](actual_value, compare_value)


def _validate_cmd_spec(cmd_spec: dict, i: int, stage: str, is_first: bool) -> bool:
    """Check if command should run at this stage, warn on unknown stages."""
    cmd_stage = cmd_spec.get("stage")
    if is_first and cmd_stage and cmd_stage not in VALID_STAGES:
        typer.secho(
            f"  ⚠  extra_command[{i}]: unknown stage '{cmd_stage}' (valid: {', '.join(sorted(VALID_STAGES))})",
            fg=typer.colors.YELLOW,
        )
    return cmd_stage == stage


def _print_cmd_info(cmd_spec: dict, stage: str, verbose: bool):
    """Print verbose info about command execution."""
    if not verbose:
        return
    when_marker = cmd_spec.get("when", "")
    extra_env = cmd_spec.get("env")
    typer.secho(f"\n  📋 Running extra command (stage: {stage})", fg=typer.colors.CYAN)
    if when_marker:
        typer.secho(f"     Condition: {when_marker}", fg=typer.colors.CYAN, dim=True)
    if extra_env and isinstance(extra_env, dict):
        env_str = " ".join(f"{k}={v}" for k, v in extra_env.items())
        typer.secho(f"     Environment: {env_str}", fg=typer.colors.CYAN, dim=True)


def _handle_cmd_error(command: list, stage: str, when_marker: str, extra_env: dict | None):
    """Print error details and exit."""
    typer.secho(f"\n  ✗ Extra command failed at stage '{stage}':", fg=typer.colors.RED)
    typer.secho(f"    Command: {' '.join(command)}", fg=typer.colors.RED)
    if when_marker:
        typer.secho(f"    Condition: {when_marker}", fg=typer.colors.RED)
    if extra_env:
        env_str = " ".join(f"{k}={v}" for k, v in extra_env.items())
        typer.secho(f"    Environment: {env_str}", fg=typer.colors.RED)
    sys.exit(1)


def _run_commands_for_stage(
    stage: str,
    extra_commands: list[dict] | None,
    odoo_version: str,
    python_version: str | None,
    venv_dir: Path,
    verbose: bool,
):
    """Run extra commands for a specific stage.

    Args:
        stage: The stage to run commands for (e.g., 'after_venv', 'after_requirements')
        extra_commands: List of command dicts with 'command', 'when', 'stage', and optionally 'env' keys
        odoo_version: The Odoo version
        python_version: The Python version
        venv_dir: The virtual environment directory
        verbose: Whether to print verbose output
    """
    if not extra_commands:
        return

    for i, cmd_spec in enumerate(extra_commands):
        is_first = i == 0
        if not _validate_cmd_spec(cmd_spec, i, stage, is_first):
            continue

        # Check if the 'when' marker evaluates to True
        when_marker = cmd_spec.get("when", "")
        if not _evaluate_marker(when_marker, odoo_version, python_version):
            continue

        command = cmd_spec.get("command")
        if not command or not isinstance(command, list):
            typer.secho(
                f"  ⚠  extra_command[{i}]: missing or invalid 'command' field, skipping",
                fg=typer.colors.YELLOW,
            )
            continue

        extra_env = cmd_spec.get("env")
        if extra_env and isinstance(extra_env, dict):
            # Convert values to strings
            extra_env = {k: str(v) for k, v in extra_env.items()}

        _print_cmd_info(cmd_spec, stage, verbose)

        try:
            _run_command(command, venv_dir=venv_dir, verbose=verbose, extra_env=extra_env)
        except SystemExit:
            _handle_cmd_error(command, stage, when_marker, extra_env)


def _resolve_manifest_dep(dep: str) -> str:
    """Translate a manifest python dependency to its pip package name.

    In Odoo <= 12.0 external_dependencies.python entries are importable module names
    (e.g. ``stdnum``) because the loader validated them via importlib.import_module.
    See: https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/models/ir_module.py#L316-L331

    Starting from 13.0 they should be pip package names, but many modules (especially
    OCA ports) still use import names in practice, so the mapping is applied unconditionally.

    >>> _resolve_manifest_dep("stdnum")
    'python-stdnum'
    >>> _resolve_manifest_dep("Crypto")
    'pycryptodome'
    >>> _resolve_manifest_dep("dateutil")
    'python-dateutil'
    >>> _resolve_manifest_dep("unknown_pkg")
    'unknown_pkg'
    """
    return _MANIFEST_IMPORT_TO_PIP.get(dep.lower(), dep)


def _collect_constrained_packages(req_lines: list[str], target_env: dict[str, str]) -> set[str]:
    """Return lowercase names of packages that appear with a version specifier.

    Used to auto-detect user requirements that conflict with Odoo's pinned versions,
    so Odoo's pin can be skipped in favour of the user's constraint.

    >>> _collect_constrained_packages(["python-stdnum>=1.9", "debugpy", "# comment"], {})
    {'python-stdnum'}
    >>> _collect_constrained_packages(["python-stdnum", "foo==1.0"], {})
    {'foo'}
    """
    result = set()
    for line in req_lines:
        line = line.split("#")[0].strip()
        if not line:
            continue
        try:
            req = Requirement(line)
            if req.specifier and (not req.marker or req.marker.evaluate(environment=target_env)):
                result.add(req.name.lower())
        except InvalidRequirement:
            pass
    return result


def _collect_mentioned_packages(req_lines: list[str], target_env: dict[str, str]) -> set[str]:
    """Return lowercase names of all packages mentioned (with or without a version specifier).

    Used to detect packages whose known transitive dependencies conflict with Odoo's pins,
    even when the package itself carries no version modifier.

    >>> sorted(_collect_mentioned_packages(["matplotlib", "debugpy==1.0", "# comment"], {}))
    ['debugpy', 'matplotlib']
    >>> _collect_mentioned_packages(["foo ; sys_platform == 'win32'"], {"sys_platform": "linux"})
    set()
    """
    result = set()
    for line in req_lines:
        line = line.split("#")[0].strip()
        if not line:
            continue
        try:
            req = Requirement(line)
            if not req.marker or req.marker.evaluate(environment=target_env):
                result.add(req.name.lower())
        except InvalidRequirement:
            pass
    return result


def _scan_extra_sources(
    collector_fn: Callable[[list[str], dict[str, str]], set[str]],
    extra_requirements: list[str] | None,
    extra_requirements_file: str | None,
    target_env: dict[str, str],
) -> set[str]:
    """Scan only extra_requirements and extra_requirements_file.

    Used by auto-ignore logic to detect packages that the user/preset explicitly
    overrides.  Addons dirs and manifests are excluded because they are installation
    targets, not overrides.
    """
    result: set[str] = set()

    if extra_requirements:
        result |= collector_fn(extra_requirements, target_env)

    if extra_requirements_file:
        path = Path(extra_requirements_file).expanduser().resolve()
        if path.exists():
            result |= collector_fn(path.read_text(encoding="utf-8").splitlines(), target_env)

    return result


def _keep_if_marker_matches(req_line: str, env: dict | None = None) -> str | None:
    req_line = req_line.split("#")[0].strip()
    if not req_line:
        return None
    req = Requirement(req_line)

    if req.marker and not req.marker.evaluate(environment=env):
        return None

    # extras = f"[{','.join(sorted(req.extras))}]" if req.extras else ""
    spec = str(req.specifier)  # e.g. "==22.10.2"
    return f"{req.name}{spec}"


def _is_ignored(req_name: str, req: Requirement | None, ignored_req_map: dict) -> bool:
    """Check if a requirement should be ignored based on the ignored_req_map."""
    req_name_normalized = re.sub(r"[-_.]", "-", req_name.lower())
    if req_name_normalized not in ignored_req_map:
        return False
    if req is None:
        # Unparseable line — ignore if the bare name matches
        return True
    for ignored_req in ignored_req_map[req_name_normalized]:
        if not ignored_req.specifier or (req.specifier and (req.specifier & ignored_req.specifier) == req.specifier):
            return True
    return False


def _parse_req_line(
    raw_line: str,
    target_env: dict[str, str],
) -> tuple[str | None, Requirement | None]:
    """Parse a requirement line, applying marker filtering.

    Returns (clean_line, parsed_req) or (None, None) if the line should be skipped.
    For InvalidRequirement lines, returns (raw_line, None) so they pass through.
    """
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None, None

    try:
        valid_line = _keep_if_marker_matches(line, env=target_env)
        if not valid_line:
            return None, None
        return valid_line, Requirement(valid_line)
    except InvalidRequirement:
        # Can't parse — pass through raw (e.g. URL-based requirements)
        return line, None


def _tag_and_add(
    req_map: dict[str, list[TaggedRequirement]],
    raw_line: str,
    req: Requirement | None,
    source: ReqSource,
    origin: str,
    ignored_req_map: dict,
):
    """Add a tagged requirement to the map, skipping ignored packages.

    PRESET entries are never filtered — they represent explicit user/preset overrides
    and must always pass through (the old code passed ignored_req_map={} for them).
    """
    if req is not None:
        pkg_key = re.sub(r"[-_.]", "-", req.name.lower())
        if source != ReqSource.PRESET and _is_ignored(req.name, req, ignored_req_map):
            return
    else:
        match = PKG_NAME_PATTERN.match(raw_line)
        if match:
            pkg_key = re.sub(r"[-_.]", "-", match.group("lib_name").lower())
            if source != ReqSource.PRESET and pkg_key in ignored_req_map:
                return
        else:
            pkg_key = raw_line.strip().lower()

    req_map[pkg_key].append(TaggedRequirement(raw_line=raw_line, requirement=req, source=source, origin=origin))


def _collect_from_files(
    req_map: dict[str, list[TaggedRequirement]],
    files: list[Path],
    source: ReqSource,
    ignored_req_map: dict,
    target_env: dict[str, str],
):
    """Collect requirements from requirement files into the map."""
    for req_file in files:
        with open(req_file, encoding="utf-8") as f:
            for line in f:
                clean, req = _parse_req_line(line, target_env)
                if clean is not None:
                    _tag_and_add(req_map, clean, req, source, str(req_file), ignored_req_map)


def _collect_manifest_deps(
    manifest_files: list[Path],
    parsed_manifests: dict[Path, dict],
    req_map: dict[str, list[TaggedRequirement]],
    known_packages: set[str],
    ignored_req_map: dict,
    target_env: dict[str, str],
) -> list[str]:
    """Collect manifest external_dependencies, splitting overlapping vs manifest-only.

    Deps already in req_map (from req files/presets) are added to the main map
    for conflict resolution. Deps only in manifests are returned for best-effort install.
    """
    manifest_only_deps: list[str] = []
    for mf in manifest_files:
        ext_deps = parsed_manifests[mf].get("external_dependencies", {})
        if not isinstance(ext_deps.get("python"), list):
            continue
        for dep in ext_deps["python"]:
            resolved_dep = _resolve_manifest_dep(dep)
            clean, req = _parse_req_line(resolved_dep, target_env)
            if clean is None:
                continue
            # Determine normalised key and check if ignored
            if req is not None:
                pkg_key = re.sub(r"[-_.]", "-", req.name.lower())
                if _is_ignored(req.name, req, ignored_req_map):
                    continue
            else:
                match = PKG_NAME_PATTERN.match(clean)
                pkg_key = re.sub(r"[-_.]", "-", match.group("lib_name").lower()) if match else clean.strip().lower()
                if pkg_key in ignored_req_map:
                    continue

            if pkg_key in known_packages:
                _tag_and_add(req_map, clean, req, ReqSource.ADDON, str(mf), ignored_req_map)
            else:
                manifest_only_deps.append(clean)
    return manifest_only_deps


def _collect_all_requirements(
    base_req_files: list[Path],
    addons_req_files: list[Path],
    extra_requirements: list[str] | None,
    extra_requirements_file: str | None,
    manifest_files: list[Path],
    parsed_manifests: dict[Path, dict],
    ignored_req_map: dict,
    target_env: dict[str, str],
) -> tuple[dict[str, list[TaggedRequirement]], list[str]]:
    """Collect all requirements from every source into a map keyed by normalised package name.

    Sources are tagged so conflict resolution can apply priority rules:
    - BASE: Odoo's requirements.txt
    - ADDON: OCA addons dir requirements.txt + manifest external_dependencies
    - PRESET: extra_requirements / extra_requirements_file

    Manifest deps that don't overlap with any req file are returned separately
    in ``manifest_only_deps`` — they'll be installed best-effort (one-by-one,
    skipping failures) since they may need system C libraries.

    Returns:
        (req_map, manifest_only_deps)
    """
    req_map: dict[str, list[TaggedRequirement]] = defaultdict(list)

    # 1. Odoo's own requirements.txt (BASE)
    _collect_from_files(req_map, base_req_files, ReqSource.BASE, ignored_req_map, target_env)

    # 2. OCA addons dir requirements.txt (ADDON — OCA-maintained, not Odoo core)
    _collect_from_files(req_map, addons_req_files, ReqSource.ADDON, ignored_req_map, target_env)

    # 3. Preset extra_requirements (PRESET)
    if extra_requirements:
        for req_line in extra_requirements:
            clean, req = _parse_req_line(req_line, target_env)
            if clean is not None:
                _tag_and_add(req_map, clean, req, ReqSource.PRESET, "extra_requirements", ignored_req_map)

    # 4. Preset extra_requirements_file (PRESET)
    if extra_requirements_file:
        extra_req_path = Path(extra_requirements_file).expanduser().resolve()
        if extra_req_path.exists():
            _collect_from_files(req_map, [extra_req_path], ReqSource.PRESET, ignored_req_map, target_env)

    # 5. Split manifest deps: overlapping ones go to req_map, rest to manifest_only
    known_packages = set(req_map.keys())
    manifest_only_deps = _collect_manifest_deps(
        manifest_files,
        parsed_manifests,
        req_map,
        known_packages,
        ignored_req_map,
        target_env,
    )

    return dict(req_map), manifest_only_deps


def _specifiers_conflict(a: Requirement, b: Requirement) -> bool:
    """Return True if no version can satisfy both a and b simultaneously.

    Handles common cases:
    - ==X vs ==Y (different exact pins)
    - ==X vs >=Y (exact pin doesn't satisfy range)
    - Two ranges with empty intersection

    Returns False (no conflict) when either requirement has no specifier,
    since bare names are compatible with anything.

    >>> _specifiers_conflict(Requirement("pkg==1.8"), Requirement("pkg>=1.16"))
    True
    >>> _specifiers_conflict(Requirement("pkg==2.20.0"), Requirement("pkg==2.21.0"))
    True
    >>> _specifiers_conflict(Requirement("pkg>=1.0"), Requirement("pkg>=2.0"))
    False
    >>> _specifiers_conflict(Requirement("pkg==1.8"), Requirement("pkg>=1.0,<2.0"))
    False
    >>> _specifiers_conflict(Requirement("pkg"), Requirement("pkg==1.0"))
    False
    """
    if not a.specifier or not b.specifier:
        return False

    # Extract exact pins if present (e.g. ==1.8 → "1.8")
    a_exact = _get_exact_pin(a)
    b_exact = _get_exact_pin(b)

    # Case 1: Both are exact pins — conflict if different versions
    if a_exact is not None and b_exact is not None:
        return a_exact != b_exact

    # Case 2: One is exact, other is a range — check if exact satisfies range
    if a_exact is not None:
        return not b.specifier.contains(a_exact)
    if b_exact is not None:
        return not a.specifier.contains(b_exact)

    # Case 3: Both are ranges — conservatively assume compatible
    # (full range intersection is complex; the common CI failures are exact-vs-range)
    return False


def _get_exact_pin(req: Requirement) -> str | None:
    """Extract the pinned version from a requirement like 'pkg==1.8'.

    Returns None if the requirement has no == specifier or has multiple specifiers
    beyond just ==.

    >>> _get_exact_pin(Requirement("pkg==1.8"))
    '1.8'
    >>> _get_exact_pin(Requirement("pkg>=1.0")) is None
    True
    >>> _get_exact_pin(Requirement("pkg")) is None
    True
    """
    specs = list(req.specifier)
    if len(specs) == 1 and specs[0].operator == "==":
        return specs[0].version
    return None


def _add_unique(resolved: list[str], seen: set[str], entries: list[TaggedRequirement]):
    """Append raw_lines from entries to resolved, deduplicating via seen set."""
    for e in entries:
        if e.raw_line not in seen:
            resolved.append(e.raw_line)
            seen.add(e.raw_line)


def _detect_base_addon_conflict(
    base_entries: list[TaggedRequirement],
    addon_entries: list[TaggedRequirement],
    verbose: bool,
) -> bool:
    """Check if any base entry conflicts with any addon entry. Warn if verbose."""
    for base_e in base_entries:
        for addon_e in addon_entries:
            if (
                base_e.requirement
                and addon_e.requirement
                and _specifiers_conflict(base_e.requirement, addon_e.requirement)
            ):
                if verbose:
                    typer.secho(
                        f"  ⚠  Relaxed Odoo's '{base_e.raw_line}' pin (OCA addon requires {addon_e.raw_line})",
                        fg=typer.colors.YELLOW,
                    )
                return True
    return False


def _resolve_conflicts(
    req_map: dict[str, list[TaggedRequirement]],
    verbose: bool = False,
) -> list[str]:
    """Resolve version conflicts and return final requirement lines.

    Priority rules:
    1. PRESET with version specifier wins — drop all BASE/ADDON entries for that package
    2. ADDON vs BASE conflict — drop the BASE entry, keep ADDON, warn
    3. No conflict — keep all (deduplicate identical lines)
    """
    resolved: list[str] = []
    seen: set[str] = set()

    for _pkg_name, entries in req_map.items():
        sources = {e.source for e in entries}

        # Rule 1: Versioned preset wins. Bare preset (no specifier) doesn't override.
        preset_entries = [e for e in entries if e.source == ReqSource.PRESET]
        if any(e.requirement and e.requirement.specifier for e in preset_entries):
            _add_unique(resolved, seen, preset_entries)
            continue

        # Single source type — no conflict possible
        if len(sources) == 1:
            _add_unique(resolved, seen, entries)
            continue

        # Rule 2: Mixed ADDON/BASE — check for version conflicts
        base_entries = [e for e in entries if e.source == ReqSource.BASE]
        addon_entries = [e for e in entries if e.source == ReqSource.ADDON]

        if base_entries and addon_entries and _detect_base_addon_conflict(base_entries, addon_entries, verbose):
            _add_unique(resolved, seen, addon_entries)
        else:
            _add_unique(resolved, seen, entries)

    return resolved


def _run_command(
    command: list[str],
    venv_dir: Path | None = None,
    cwd: Path | None = None,
    verbose: bool = False,
    extra_env: dict[str, str] | None = None,
    raise_on_error: bool = False,
):

    if verbose:
        typer.secho(f"  → Running: {' '.join(command)}", fg=typer.colors.BLUE)

    env = os.environ.copy()
    if venv_dir:
        env["PATH"] = str(venv_dir / "bin") + os.pathsep + env["PATH"]
        env["VIRTUAL_ENV"] = str(venv_dir)
    if extra_env:
        env.update(extra_env)

    # safe to ignore S603 as shell=False
    result = subprocess.run(  # noqa: S603
        command,
        env=env,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        if raise_on_error:
            raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)
        typer.echo(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


# Patterns to extract a failing package name from uv's error output.
# Each pattern must have a named group ``pkg``.
_UV_FAILURE_PATTERNS = [
    re.compile(r"Failed to build `(?P<pkg>[A-Za-z0-9_\-\.]+)"),
    re.compile(r"Failed to download and install `(?P<pkg>[A-Za-z0-9_\-\.]+)"),
    re.compile(r"Failed to download `(?P<pkg>[A-Za-z0-9_\-\.]+)"),
    re.compile(r"Failed to install `(?P<pkg>[A-Za-z0-9_\-\.]+)"),
    re.compile(r"error:.*`(?P<pkg>[A-Za-z0-9_\-\.]+)=="),
    re.compile(r"Because (?P<pkg>[A-Za-z0-9_\-\.]+) was not found in the package registry"),
]


def _extract_failed_package(stderr: str) -> str | None:
    """Parse uv stderr output to find the name of the package that failed to install.

    Returns the package name (without version) or None if it cannot be determined.

    >>> _extract_failed_package("Failed to build `vatnumber==1.2`")
    'vatnumber'
    >>> _extract_failed_package("Failed to download and install `lxml==4.9.3`")
    'lxml'
    >>> _extract_failed_package("Because facturx was not found in the package registry")
    'facturx'
    >>> _extract_failed_package("something went wrong with no package name") is None
    True
    """
    for pattern in _UV_FAILURE_PATTERNS:
        m = pattern.search(stderr)
        if m:
            return m.group("pkg")
    return None


def _install_requirements_with_retry(
    tmp_path: str,
    venv_dir: Path,
    verbose: bool,
    max_retries: int = 10,
) -> list[str]:
    """Attempt to install requirements, skipping packages that fail to install.

    On each failure, parses uv's stderr to identify the offending package,
    removes it from the requirements file, and retries. If the failing package
    cannot be determined, exits with an error.

    Returns the list of package names that were skipped.
    """
    skipped: list[str] = []
    skipped_normalized: set[str] = set()

    for attempt in range(max_retries + 1):
        install_args = ["uv", "pip", "install", "-r", tmp_path]
        try:
            _run_command(
                install_args,
                venv_dir=venv_dir,
                verbose=False,
                raise_on_error=True,
                extra_env={"UV_PRERELEASE": "allow"},
            )
        except subprocess.CalledProcessError as exc:
            if attempt == max_retries:
                typer.echo(exc.stderr, file=sys.stderr)
                typer.secho(
                    f"  ✗ Installation still failing after skipping {len(skipped)} package(s). Giving up.",
                    fg=typer.colors.RED,
                )
                sys.exit(1)

            pkg = _extract_failed_package(exc.stderr)
            if pkg is not None:
                # Normalise name: treat hyphens, underscores and dots as equivalent
                # so that e.g. "rfc6266-parser" matches "rfc6266_parser" in the file.
                pkg_normalized = re.sub(r"[-_.]", "-", pkg.lower())

                if pkg_normalized in skipped_normalized:
                    # Already removed this package but it still fails — it is
                    # likely pulled in as a transitive dependency and cannot be
                    # skipped at the top-level requirements level.
                    typer.echo(exc.stderr, file=sys.stderr)
                    typer.secho(
                        f"  ✗ '{pkg}' keeps failing even after being removed from requirements"
                        " (likely a transitive dependency). Giving up.",
                        fg=typer.colors.RED,
                    )
                    sys.exit(1)

                typer.echo(exc.stderr, file=sys.stderr)
                typer.secho(
                    f"  ⚠  '{pkg}' failed to install — skipping and retrying...",
                    fg=typer.colors.YELLOW,
                )
                skipped.append(pkg)
                skipped_normalized.add(pkg_normalized)

                # Rewrite the requirements file without the failing package.
                # Use normalised name comparison to handle hyphen/underscore variants.
                with open(tmp_path, encoding="utf-8") as f:
                    lines = f.readlines()
                filtered = []
                for line in lines:
                    line_pkg = line.strip().split("#")[0].strip()
                    try:
                        line_normalized = re.sub(r"[-_.]", "-", Requirement(line_pkg).name.lower())
                    except InvalidRequirement:
                        match = PKG_NAME_PATTERN.match(line_pkg)
                        line_normalized = re.sub(r"[-_.]", "-", match.group("lib_name").lower()) if match else None
                    if line_normalized != pkg_normalized:
                        filtered.append(line)
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.writelines(filtered)
            else:
                typer.echo(exc.stderr, file=sys.stderr)
                typer.secho(
                    "  ✗ Could not detect which package failed to install."
                    " Retry without --skip-on-failure for full error details.",
                    fg=typer.colors.RED,
                )
                sys.exit(1)
        else:
            return skipped

    return skipped  # unreachable, satisfies type checker


def _install_manifest_deps_best_effort(
    deps: list[str],
    venv_dir: Path,
    verbose: bool,
) -> list[str]:
    """Install manifest-only deps one-by-one, skipping failures.

    Manifest deps may require system C libraries (e.g. python-ldap, pymssql).
    Installing them individually means one failure doesn't block the rest.

    Returns list of deps that failed to install.
    """
    skipped: list[str] = []
    for dep in deps:
        try:
            _run_command(
                ["uv", "pip", "install", dep],
                venv_dir=venv_dir,
                verbose=False,
                raise_on_error=True,
                extra_env={"UV_PRERELEASE": "allow"},
            )
        except subprocess.CalledProcessError:
            skipped.append(dep)
            typer.secho(
                f"  ⚠  '{dep}' failed to install (may need system libraries) — skipping",
                fg=typer.colors.YELLOW,
            )
    return skipped


# Pattern to extract the conflicting pin from uv pip compile's error output.
# Uses \s+ between "you" and "require" because uv wraps long lines, e.g.:
#   "and you\n      require pyparsing==2.2.0, we can conclude ..."
# Version is [\w.]+ (not \S+) to avoid capturing trailing commas/punctuation.
_UV_CONFLICT_PATTERN = re.compile(r"you\s+require\s+(\S+)==([\w.]+)")


def _validate_and_relax(
    req_file_path: str,
    python_version: str | None,
    base_pins: set[str],
    verbose: bool = False,
    max_retries: int = 5,
) -> set[str]:
    """Validate requirements via uv pip compile, relaxing base pins on transitive conflict.

    Runs ``uv pip compile`` to resolve the full dependency tree.  If it fails
    due to a version conflict involving a BASE-sourced pin, removes that pin
    from the requirements file and retries.

    Returns:
        Set of normalised package names whose base pins were removed.
    """
    relaxed: set[str] = set()

    for _attempt in range(max_retries):
        cmd = ["uv", "pip", "compile", req_file_path, "--quiet"]
        if python_version:
            cmd += ["--python", python_version]

        result = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
        if result.returncode == 0:
            return relaxed  # requirements are solvable

        match = _UV_CONFLICT_PATTERN.search(result.stderr)
        if not match:
            break  # can't parse error — fall through to normal install

        pkg_raw, pin_version = match.group(1), match.group(2)
        pkg_normalized = re.sub(r"[-_.]", "-", pkg_raw.lower())

        if pkg_normalized not in base_pins:
            break  # not a base pin — can't auto-relax

        # Remove the conflicting line from the requirements file
        with open(req_file_path, encoding="utf-8") as f:
            lines = f.readlines()
        filtered = []
        for line in lines:
            line_pkg = line.strip().split("#")[0].strip()
            if not line_pkg:
                filtered.append(line)
                continue
            try:
                line_normalized = re.sub(r"[-_.]", "-", Requirement(line_pkg).name.lower())
            except InvalidRequirement:
                line_match = PKG_NAME_PATTERN.match(line_pkg)
                line_normalized = re.sub(r"[-_.]", "-", line_match.group("lib_name").lower()) if line_match else None
            if line_normalized != pkg_normalized:
                filtered.append(line)
        with open(req_file_path, "w", encoding="utf-8") as f:
            f.writelines(filtered)

        relaxed.add(pkg_normalized)
        typer.secho(
            f"  ⚠  Relaxed Odoo's '{pkg_raw}=={pin_version}' pin (transitive conflict detected by uv)",
            fg=typer.colors.YELLOW,
        )

    return relaxed


# Packages that cannot be installed in an isolated build environment (they rely on
# build tools already present in the venv).  Detected in any requirement source
# (Odoo's own requirements.txt, addons dirs, user sources, manifests), excluded from
# the batch install, and re-installed afterwards with --no-build-isolation.
# Format: { normalised_pkg_name: when_marker }  (empty when_marker = always apply)
_NO_BUILD_ISOLATION_PACKAGES: dict[str, str] = {
    "vatnumber": "odoo_version <= '13.0'",
    "suds-jurko": "odoo_version <= '13.0'",
    # magento depends on suds-jurko, so the transitive build of suds-jurko also
    # needs the legacy setuptools already present in the venv.
    "magento": "odoo_version <= '13.0'",
    "rfc6266-parser": "",
}

# Hidden build-time dependencies that must be pre-installed in the venv before a
# --no-build-isolation install can succeed.  These are not declared by the package
# itself (hence "hidden") and are not part of the regular requirements.
# Format: { normalised_pkg_name: [build_dep, ...] }
_NBI_BUILD_DEPS: dict[str, list[str]] = {}


def _collect_no_build_isolation_specs(
    req_lines: list[str],
    target_env: dict[str, str],
    odoo_version: str,
    python_version: str | None,
) -> dict[str, str]:
    """Return {normalised_name: install_spec} for packages that need --no-build-isolation.

    Evaluates both the requirement's own environment marker and the package-level
    when marker from ``_NO_BUILD_ISOLATION_PACKAGES``.

    >>> _collect_no_build_isolation_specs(["rfc6266-parser==0.0.7", "requests"], {}, "17.0", None)
    {'rfc6266-parser': 'rfc6266-parser==0.0.7'}
    >>> _collect_no_build_isolation_specs(["rfc6266_parser==0.0.6", "requests"], {}, "17.0", None)
    {'rfc6266-parser': 'rfc6266_parser==0.0.6'}
    >>> _collect_no_build_isolation_specs(["vatnumber", "requests"], {}, "14.0", None)
    {}
    >>> _collect_no_build_isolation_specs(["magento==3.1", "requests"], {}, "12.0", None)
    {'magento': 'magento==3.1'}
    >>> _collect_no_build_isolation_specs(["magento==3.1", "requests"], {}, "14.0", None)
    {}
    >>> _collect_no_build_isolation_specs(["vatnumber==1.2", "requests"], {}, "13.0", None)
    {'vatnumber': 'vatnumber==1.2'}
    """
    result: dict[str, str] = {}
    for line in req_lines:
        line = line.split("#")[0].strip()
        if not line:
            continue
        try:
            req = Requirement(line)
            pkg_normalized = re.sub(r"[-_.]", "-", req.name.lower())
            if pkg_normalized not in _NO_BUILD_ISOLATION_PACKAGES:
                continue
            if req.marker and not req.marker.evaluate(environment=target_env):
                continue
            when_marker = _NO_BUILD_ISOLATION_PACKAGES[pkg_normalized]
            if _evaluate_marker(when_marker, odoo_version, python_version):
                result[pkg_normalized] = f"{req.name}{req.specifier}"
        except InvalidRequirement:
            pass
    return result


def _get_python_version_from_odoo_src(odoo_dir: Path) -> str | None:
    init_py = odoo_dir / "odoo" / "__init__.py"
    if not init_py.is_file():
        return None

    content = init_py.read_text()
    match = re.search(r"MIN_PY_VERSION\s*=\s*\((\d+),\s*(\d+)\)", content)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return None


def _find_manifest_files(addons_paths: list[str]) -> list[Path]:
    manifest_files = []
    for path in addons_paths:
        for root, _, files in os.walk(path):
            if "__manifest__.py" in files:
                manifest_files.append(Path(root) / "__manifest__.py")
    return manifest_files


def _process_requirement_line(
    req_line: str,
    ignored_req_map: dict,
    tmp_file,
    target_env_for_markers: dict[str, str],
) -> bool:
    req_line = req_line.strip()
    if not req_line or req_line.startswith("#"):
        return False

    try:
        valid_line = _keep_if_marker_matches(req_line, env=target_env_for_markers)
        if not valid_line:
            return False

        req = Requirement(valid_line)

        should_ignore = False
        req_name_normalized = re.sub(r"[-_.]", "-", req.name.lower())
        if req_name_normalized in ignored_req_map:
            for ignored_req in ignored_req_map[req_name_normalized]:
                if not ignored_req.specifier or (
                    req.specifier and (req.specifier & ignored_req.specifier) == req.specifier
                ):
                    should_ignore = True
                    break

        if should_ignore:
            return False
        else:
            tmp_file.write(valid_line + "\n")
            return True

    except InvalidRequirement:
        match = PKG_NAME_PATTERN.match(req_line)
        if match and match.group("lib_name").lower().strip() in ignored_req_map:
            return False
        else:
            tmp_file.write(req_line + "\n")
            return True


def create_odoo_venv(  # noqa: C901
    odoo_version: str,
    odoo_dir: Path | str,
    venv_dir: Path | str,
    python_version: str | None,
    install_odoo: bool = True,
    install_odoo_requirements: bool = True,
    ignore_from_odoo_requirements: str | None = None,
    addons_paths: list[str] | None = None,
    install_addons_dirs_requirements: bool = False,
    ignore_from_addons_dirs_requirements: str | None = None,
    install_addons_manifests_requirements: bool = False,
    ignore_from_addons_manifests_requirements: str | None = None,
    extra_requirements_file: str | None = None,
    extra_requirements: list[str] | None = None,
    extra_commands: list[dict] | None = None,
    verbose: bool = False,
    skip_on_failure: bool = False,
):
    odoo_dir = Path(odoo_dir).expanduser().resolve()
    venv_dir = Path(venv_dir).expanduser().resolve()

    # 1. Determine Python version
    if not python_version:
        python_version = _get_python_version_from_odoo_src(odoo_dir)

    # uv does not support older Python version
    # https://github.com/astral-sh/uv/issues/9833
    if python_version:
        py_major_minor = ".".join(python_version.split(".")[:2])
        if parse_version(py_major_minor) < parse_version("3.7"):
            typer.secho(
                f"error: Invalid version request: Python <3.7 is not supported but {python_version} was requested.",
                fg=typer.colors.RED,
            )
            sys.exit(1)

    current_default_env = default_environment()
    target_env_for_markers: dict[str, str] = {k: str(v) for k, v in current_default_env.items()}
    if python_version:
        target_env_for_markers["python_version"] = ".".join(python_version.split(".")[:2])
        target_env_for_markers["python_full_version"] = python_version
    else:
        target_env_for_markers["python_version"] = current_default_env["python_version"]
        target_env_for_markers["python_full_version"] = current_default_env["python_full_version"]

    # 2. Create virtual environment
    typer.secho("Creating virtual environment...")
    if python_version:
        found = subprocess.run(  # noqa: S603
            ["uv", "python", "find", python_version],  # noqa: S607
            capture_output=True,
        )
        if found.returncode != 0:
            _run_command(
                ["uv", "python", "install", python_version],
                verbose=verbose,
            )
    venv_command = ["uv", "venv", str(venv_dir)]
    if python_version:
        venv_command.extend(["--python", python_version])
    _run_command(venv_command, verbose=verbose)
    typer.secho(
        f"  ✔ Virtual environment created at {typer.style(str(venv_dir), fg=typer.colors.YELLOW)}",
    )

    # Run extra commands for 'after_venv' stage
    _run_commands_for_stage(
        "after_venv",
        extra_commands,
        odoo_version,
        python_version,
        venv_dir,
        verbose,
    )

    # 3. Process requirements
    # Separate Odoo's own requirements (BASE) from OCA addons dir requirements (ADDON).
    # Addons dir requirements.txt are OCA-maintained, so on conflict they take priority
    # over Odoo's pins — hence they are classified as ADDON, not BASE.
    odoo_req_files: list[Path] = []
    addons_req_files: list[Path] = []
    if install_odoo_requirements:
        odoo_reqs_file = odoo_dir / "requirements.txt"
        if odoo_reqs_file.exists():
            odoo_req_files.append(odoo_reqs_file)

    if install_addons_dirs_requirements and addons_paths:
        for path in addons_paths:
            addons_req_file = Path(path) / "requirements.txt"
            if addons_req_file.exists():
                addons_req_files.append(addons_req_file)

    # Combined list for backwards compat with base_pinned scanning and NBI detection
    all_req_files = odoo_req_files + addons_req_files

    ignore_req_lines = []
    if ignore_from_odoo_requirements:
        ignore_req_lines.extend([pkg.strip() for pkg in ignore_from_odoo_requirements.split(",") if pkg.strip()])
    if ignore_from_addons_dirs_requirements:
        ignore_req_lines.extend([pkg.strip() for pkg in ignore_from_addons_dirs_requirements.split(",") if pkg.strip()])
    if ignore_from_addons_manifests_requirements:
        ignore_req_lines.extend([
            pkg.strip() for pkg in ignore_from_addons_manifests_requirements.split(",") if pkg.strip()
        ])

    ignored_req_map = defaultdict(list)
    for req_line in ignore_req_lines:
        try:
            req = Requirement(req_line)
            if not req.marker or req.marker.evaluate(target_env_for_markers):
                new_req_str = f"{req.name}{req.specifier}"
                new_req = Requirement(new_req_str)
                ignored_req_map[new_req.name.lower()].append(new_req)
        except InvalidRequirement:
            typer.secho(
                f"  ⚠ Invalid requirement in ignore list: {req_line}",
                fg=typer.colors.RED,
            )

    # Hoist manifest discovery so it can be reused in both the pre-scan and the main loop.
    manifest_files: list[Path] = []
    if install_addons_manifests_requirements and addons_paths:
        manifest_files = _find_manifest_files(addons_paths)

    # Cache parsed manifests to avoid re-reading/parsing the same files multiple times.
    parsed_manifests: dict[Path, dict] = {mf: ast.literal_eval(mf.read_text(encoding="utf-8")) for mf in manifest_files}

    # Collect the set of packages actually present in the base requirement files
    # (Odoo's requirements.txt and addons dirs).  Auto-ignore logic is restricted to
    # this set so we never silently drop a package that Odoo doesn't pin.
    base_pinned: set[str] = set()
    for req_file in all_req_files:
        base_pinned |= _collect_mentioned_packages(
            req_file.read_text(encoding="utf-8").splitlines(), target_env_for_markers
        )

    # Pre-scan user sources for packages with version specifiers.
    # When a user source pins/constrains a package that Odoo also pins, Odoo's stricter
    # pin is skipped automatically so the user's version wins without an explicit ignore entry.
    #
    # Only extra_requirements and extra_requirements_file are considered "override sources"
    # for auto-ignore.  Addons dirs requirements.txt and manifests are NOT — they are
    # targets of installation, not overrides.  Including them causes a bug where a package
    # like bokeh (present in both an addons dir requirements.txt and its manifest) gets
    # auto-ignored from base_pinned, which then also drops it from the manifest install.
    user_constrained = _scan_extra_sources(
        _collect_constrained_packages, extra_requirements, extra_requirements_file, target_env_for_markers
    )
    for pkg_name in user_constrained & base_pinned:
        if not any(not r.specifier for r in ignored_req_map[pkg_name]):
            ignored_req_map[pkg_name].append(Requirement(pkg_name))
            if verbose:
                typer.secho(
                    f"  i  Auto-ignoring Odoo's '{pkg_name}' pin (overridden by user requirement)",
                    fg=typer.colors.CYAN,
                )

    # Detect packages that require --no-build-isolation from all requirement sources.
    # They are excluded from the batch install and installed separately afterwards.
    _nbi_args = (target_env_for_markers, odoo_version, python_version)
    no_build_isolation_specs: dict[str, str] = {}
    for req_file in all_req_files:
        no_build_isolation_specs.update(
            _collect_no_build_isolation_specs(req_file.read_text(encoding="utf-8").splitlines(), *_nbi_args)
        )
    if extra_requirements:
        no_build_isolation_specs.update(_collect_no_build_isolation_specs(extra_requirements, *_nbi_args))
    if extra_requirements_file:
        _extra_req_path = Path(extra_requirements_file).expanduser().resolve()
        if _extra_req_path.exists():
            no_build_isolation_specs.update(
                _collect_no_build_isolation_specs(_extra_req_path.read_text(encoding="utf-8").splitlines(), *_nbi_args)
            )
    for mf in manifest_files:
        ext_deps = parsed_manifests[mf].get("external_dependencies", {})
        if isinstance(ext_deps.get("python"), list):
            no_build_isolation_specs.update(_collect_no_build_isolation_specs(ext_deps["python"], *_nbi_args))
    for pkg_name in no_build_isolation_specs:
        ignored_req_map[pkg_name].append(Requirement(pkg_name))
        if verbose:
            typer.secho(
                f"  i  Auto-ignoring '{pkg_name}' (will install separately with --no-build-isolation)",
                fg=typer.colors.CYAN,
            )

    # Collect → Resolve → Write pipeline
    req_map, manifest_only_deps = _collect_all_requirements(
        base_req_files=odoo_req_files,
        addons_req_files=addons_req_files,
        extra_requirements=extra_requirements,
        extra_requirements_file=extra_requirements_file,
        manifest_files=manifest_files,
        parsed_manifests=parsed_manifests,
        ignored_req_map=ignored_req_map,
        target_env=target_env_for_markers,
    )

    # Resolve conflicts (Phase 2 — priority: PRESET > ADDON > BASE)
    resolved_lines = _resolve_conflicts(req_map, verbose=verbose)

    # Collect BASE-sourced package names so _validate_and_relax() knows which pins are safe to drop
    base_pin_names = {
        re.sub(r"[-_.]", "-", pkg.lower())
        for pkg, entries in req_map.items()
        if any(e.source == ReqSource.BASE for e in entries)
    }

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as tmp:
        tmp_path = tmp.name
        for line in resolved_lines:
            tmp.write(line + "\n")
        req_count = len(resolved_lines)

    # Validate the full dependency tree via uv pip compile — relax BASE pins
    # that cause transitive conflicts (replaces the old _KNOWN_TRANSITIVE_CONFLICTS dict)
    relaxed = _validate_and_relax(
        req_file_path=tmp_path,
        python_version=python_version,
        base_pins=base_pin_names,
        verbose=verbose,
    )
    if relaxed:
        with open(tmp_path, encoding="utf-8") as f:
            req_count = sum(1 for line in f if line.strip())

    skipped: list[str] = []
    if req_count > 0:
        typer.secho("\nInstalling required packages...")
        if verbose:
            if ignored_req_map:
                typer.secho(
                    "   Packages to ignore:",
                    fg=typer.colors.BLUE,
                )
                for pkg_name in sorted(ignored_req_map.keys()):
                    for req in ignored_req_map[pkg_name]:
                        typer.secho(f"      - {req}", fg=typer.colors.YELLOW)
            with open(tmp_path, encoding="utf-8") as f:
                requirements = f.read().splitlines()
                typer.secho("   Packages to install:", fg=typer.colors.BLUE)
                for req in requirements:
                    typer.secho(f"      - {req}", fg=typer.colors.CYAN)

        if skip_on_failure:
            skipped = _install_requirements_with_retry(tmp_path, venv_dir=venv_dir, verbose=verbose)
            if skipped:
                typer.secho(
                    f"  ⚠  Skipped {len(skipped)} package(s) due to installation failure: "
                    + ", ".join(typer.style(p, fg=typer.colors.YELLOW) for p in skipped),
                    fg=typer.colors.YELLOW,
                )
        else:
            _run_command(
                ["uv", "pip", "install", "-r", tmp_path],
                venv_dir=venv_dir,
                verbose=False,
                extra_env={"UV_PRERELEASE": "allow"},
            )
        typer.secho(f"  ✔  {typer.style(req_count, fg=typer.colors.YELLOW)} Packages installed successfully")

    os.remove(tmp_path)

    # Best-effort install for manifest-only deps (not in any requirements.txt).
    # These are installed individually so one failure (e.g. python-ldap needing
    # system C libs) doesn't block the rest.
    if manifest_only_deps:
        # Filter out NBI packages — they're handled separately with --no-build-isolation
        nbi_names = set(no_build_isolation_specs.keys())
        manifest_only_deps = [d for d in manifest_only_deps if _normalize_pkg_name(d) not in nbi_names]

    if manifest_only_deps:
        typer.secho(f"\nInstalling {len(manifest_only_deps)} manifest dependencies (best-effort)...")
        if verbose:
            for dep in manifest_only_deps:
                typer.secho(f"      - {dep}", fg=typer.colors.CYAN)
        manifest_skipped = _install_manifest_deps_best_effort(manifest_only_deps, venv_dir=venv_dir, verbose=verbose)
        installed_count = len(manifest_only_deps) - len(manifest_skipped)
        if installed_count > 0:
            typer.secho(f"  ✔  {installed_count} manifest dependencies installed")
        if manifest_skipped:
            typer.secho(
                f"  ⚠  {len(manifest_skipped)} manifest dependencies skipped (may need system libraries)",
                fg=typer.colors.YELLOW,
            )

    # Odoo <= 13.0 requires setuptools<58 (2to3 support removed in 58.0) and wheel
    # as build tools for packages like vatnumber that use the legacy setup.py build system.
    if _evaluate_marker("odoo_version <= '13.0'", odoo_version, python_version):
        typer.secho("\nInstalling legacy build tools for Odoo <= 13.0...")
        _run_command(
            ["uv", "pip", "install", "setuptools<58.0", "wheel"],
            venv_dir=venv_dir,
            verbose=verbose,
        )
        typer.secho("  ✔  setuptools<58.0 wheel installed")

    # Install packages that cannot be built in isolation (e.g. vatnumber, rfc6266-parser).
    if no_build_isolation_specs:
        typer.secho("\nInstalling packages that require --no-build-isolation...")
        for pkg_name, spec in no_build_isolation_specs.items():
            if pkg_name in _NBI_BUILD_DEPS:
                build_deps = _NBI_BUILD_DEPS[pkg_name]
                typer.secho(f"  Installing hidden build dependencies for {pkg_name}: {', '.join(build_deps)}...")
                _run_command(
                    ["uv", "pip", "install", *build_deps],
                    venv_dir=venv_dir,
                    verbose=verbose,
                )
            _run_command(
                ["uv", "pip", "install", "--no-build-isolation", spec],
                venv_dir=venv_dir,
                verbose=verbose,
            )
            typer.secho(f"  ✔  {typer.style(spec, fg=typer.colors.YELLOW)} installed (no build isolation)")

    # Installation order: venv → requirements → odoo (editable)
    _run_commands_for_stage(
        "after_requirements",
        extra_commands,
        odoo_version,
        python_version,
        venv_dir,
        verbose,
    )

    # 4. Install Odoo in editable mode
    if install_odoo:
        typer.secho("\nInstalling Odoo in editable mode...")
        _run_command(
            ["uv", "pip", "install", "-e", f"file://{odoo_dir}#egg=odoo"],
            venv_dir=venv_dir,
            verbose=verbose,
        )
        typer.secho(
            "  ✔  Installed Odoo in editable mode",
        )

        # Run extra commands for 'after_odoo_install' stage
        _run_commands_for_stage(
            "after_odoo_install",
            extra_commands,
            odoo_version,
            python_version,
            venv_dir,
            verbose,
        )

    typer.secho("\n✅ Environment setup complete!", fg=typer.colors.GREEN)
    typer.secho(
        f"Activate it with: source {typer.style(str(venv_dir / 'bin' / 'activate'), fg=typer.colors.YELLOW)}",
    )

    if skipped:
        sys.exit(1)
