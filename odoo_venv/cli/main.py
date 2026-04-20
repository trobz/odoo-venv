import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from odoo_addons_path import (
    detect_codebase_layout,
    get_addons_path,
    get_odoo_version_from_release,
)
from rich.console import Console
from rich.table import Table

from odoo_venv.exceptions import PresetNotFoundError
from odoo_venv.launcher import create_launcher
from odoo_venv.main import create_odoo_venv
from odoo_venv.utils import (
    VENV_CONFIG_FILENAME,
    load_presets,
    read_venv_config,
    split_escaped,
    write_venv_config,
)

app = typer.Typer()
# we use same python versions as OCA: https://github.com/oca/oca-ci/blob/master/.github/workflows/ci.yaml
# with some adjustments based on our experience
# we don't define a specific minor version here, but can be done via --python-version=
ODOO_PYTHON_VERSIONS = {
    "12.0": "3.7",  # faced issues with gevent and python 3.6
    "13.0": "3.7",
    "14.0": "3.8",
    "15.0": "3.8",
    "16.0": "3.10",
    "17.0": "3.10",
    "18.0": "3.10",
    "19.0": "3.10",
}


_IGNORE_PARAM_NAMES = (
    "ignore_from_odoo_requirements",
    "ignore_from_addons_dirs_requirements",
    "ignore_from_addons_manifests_requirements",
)


def _normalize_pkg_name(pkg: str) -> str:
    """Normalize a package name to match how create_odoo_venv normalizes ignore names."""
    from packaging.requirements import InvalidRequirement, Requirement

    try:
        return Requirement(pkg).name.lower()
    except InvalidRequirement:
        return pkg.lower()


def _split_ignore_packages(value: str) -> list[str]:
    """Split a comma-separated ignore string into normalized package names."""
    return [_normalize_pkg_name(p.strip()) for p in value.split(",") if p.strip()]


def _build_ignore_sources(
    ctx: typer.Context,
    preset_name: str | None,
    ignore_args: dict[str, str | None],
) -> dict[str, str]:
    """Build a mapping of {package_name: source_tag} for explicit ignores.

    Determines whether each ignored package came from a preset or a CLI argument
    by inspecting ``ctx.get_parameter_source()``.  The CLI flag name is always
    included so the user knows *which* argument caused the ignore.
    """
    import click

    sources: dict[str, str] = {}
    for param_name, value in ignore_args.items():
        if not value:
            continue
        cli_flag = f"--{param_name.replace('_', '-')}"
        is_from_preset = ctx.get_parameter_source(param_name) == click.core.ParameterSource.DEFAULT_MAP
        for normalized in _split_ignore_packages(value):
            if is_from_preset and preset_name:
                sources[normalized] = f"explicit_ignore:preset:{preset_name}:{cli_flag}"
            else:
                sources[normalized] = f"explicit_ignore:{cli_flag}"
    return sources


def _build_ignore_sources_from_config(config: dict[str, str | bool]) -> dict[str, str]:
    """Build ignore_sources from a stored .odoo-venv.toml config dict.

    Used by the ``update`` command where there's no Typer context to inspect.
    Loads the preset (if any) to determine which ignores came from it vs CLI.
    """
    preset_name = config.get("preset") or None
    preset_ignores: dict[str, set[str]] = {}  # param_name → {normalized_pkg, ...}

    if preset_name:
        all_presets = load_presets()
        if preset_name in all_presets:
            preset_data = asdict(all_presets[preset_name])
            for param_name in _IGNORE_PARAM_NAMES:
                val = preset_data.get(param_name, "") or ""
                preset_ignores[param_name] = set(_split_ignore_packages(val))

    sources: dict[str, str] = {}
    for param_name in _IGNORE_PARAM_NAMES:
        value = str(config.get(param_name, "") or "")
        cli_flag = f"--{param_name.replace('_', '-')}"
        for normalized in _split_ignore_packages(value):
            if normalized in preset_ignores.get(param_name, set()):
                sources[normalized] = f"explicit_ignore:preset:{preset_name}:{cli_flag}"
            else:
                sources[normalized] = f"explicit_ignore:{cli_flag}"
    return sources


def _apply_preset(ctx: typer.Context, preset_name: str, all_presets: dict, *, silent: bool = False):
    """Apply a preset's options to the Typer context.

    Loads preset values into ctx.default_map and stores extra_commands/extra_requirement
    in ctx.obj for later merging (so CLI flags remain additive rather than overriding).

    Args:
        ctx: Typer context to update.
        preset_name: Key in all_presets to apply.
        all_presets: Dict of loaded presets (from load_presets()).
        silent: When True, suppress the "Applying preset" message.
    """
    preset_vals = all_presets[preset_name]
    preset_options = asdict(preset_vals)

    ctx.default_map = ctx.default_map or {}
    ctx.default_map.update(preset_options)
    # Store extra_commands and extra_requirement on ctx.obj so they can be merged
    # with any explicit CLI values rather than being overridden by them.
    # Remove them from default_map so Click doesn't double-apply them.
    ctx.default_map.pop("extra_commands", None)
    ctx.default_map.pop("extra_requirement", None)
    obj = ctx.ensure_object(dict)
    obj["extra_commands"] = preset_options.get("extra_commands")
    obj["preset_extra_requirement"] = preset_options.get("extra_requirement")

    if not silent and (descr := preset_options.get("description")):
        typer.secho(f"Applying preset '{preset_name}': {descr}", fg=typer.colors.GREEN)


def preset_callback(ctx: typer.Context, param: typer.CallbackParam, value: str):
    all_presets = load_presets()

    if not value:
        obj = ctx.ensure_object(dict)
        if not obj.get("project_dir") and "common" in all_presets:
            _apply_preset(ctx, "common", all_presets)
        return None

    if value not in all_presets:
        raise PresetNotFoundError(value)

    _apply_preset(ctx, value, all_presets)
    ctx.ensure_object(dict)["explicit_preset"] = True
    return value


def project_dir_callback(ctx: typer.Context, param: typer.CallbackParam, value: str | None):
    if not value:
        return None

    # Auto-apply "project" preset silently if no explicit --preset was given.
    # Both --preset and --project-dir are is_eager, so their callbacks fire in CLI argument
    # order (not declaration order). We check explicit_preset (set by preset_callback when
    # --preset appears before --project-dir in argv) to skip the auto-apply in that case.
    # When --project-dir appears first, we apply "project" defaults silently here; if the
    # user also passed --preset, that callback fires next and will overwrite with its message.
    obj = ctx.ensure_object(dict)
    if not obj.get("explicit_preset"):
        all_presets = load_presets()
        if "project" in all_presets:
            _apply_preset(ctx, "project", all_presets, silent=True)

    obj["project_dir"] = value
    return value


def from_config_callback(ctx: typer.Context, param: typer.CallbackParam, value: str | None):
    if not value:
        return None

    path = Path(value).expanduser().resolve()
    try:
        args, _meta, _reqs, _ignored = read_venv_config(path)
    except FileNotFoundError:
        typer.secho(f"error: config file not found at {path}", fg=typer.colors.RED)
        raise typer.Exit(1) from None

    # If TOML specifies a preset, apply it first (lowest precedence)
    preset_name = args.get("preset")
    if preset_name:
        all_presets = load_presets()
        if preset_name in all_presets:
            _apply_preset(ctx, preset_name, all_presets, silent=True)

    # Overlay TOML args onto default_map (preset defaults < TOML values < CLI flags)
    ctx.default_map = ctx.default_map or {}
    # Remap TOML keys to CLI param names where they differ
    key_remap = {"create_launcher": "create_launcher_flag"}
    for key, val in args.items():
        if key == "preset":
            continue  # already applied above
        if val != "" and val is not None:
            mapped_key = key_remap.get(key, key)
            ctx.default_map[mapped_key] = val
    return value


def version_callback(value: bool):
    if value:
        typer.echo(f"odoo-venv {version('odoo-venv')}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Display the odoo-venv version.",
        ),
    ] = False,
):
    pass


def _build_extra_requirements(ctx: typer.Context, extra_requirement: str | tuple | None) -> list[str]:
    """Merge preset's extra_requirement with any explicit CLI value."""
    result = []
    preset_extra_req = (ctx.obj or {}).get("preset_extra_requirement")
    if preset_extra_req:
        result.extend(split_escaped(preset_extra_req))
    if extra_requirement:
        if isinstance(extra_requirement, str):
            result.extend(split_escaped(extra_requirement))
        else:
            result.extend(extra_requirement)
    return result


def _detect_project_layout(project_dir_value: str) -> tuple[Path | None, str | None, str | None]:
    """Detect odoo_dir, odoo_version, and addons_path from a project directory.

    Returns:
        (odoo_dir_path, odoo_version, addons_path) — any value may be None if not detected.
    """
    project_dir_path = Path(project_dir_value).expanduser().resolve()
    detected_paths = detect_codebase_layout(project_dir_path)

    addons_path = get_addons_path(project_dir_path, detected_paths=detected_paths)

    # Resolve odoo_dir from detected layout
    odoo_dir_path = None
    if detected_paths.get("odoo_dir"):
        odoo_dir_path = detected_paths["odoo_dir"][0].parent

    # Infer version from release.py inside the detected odoo dir
    odoo_version = None
    if odoo_dir_path:
        odoo_version = get_odoo_version_from_release(odoo_dir_path)

    return odoo_dir_path, odoo_version, addons_path


def _resolve_odoo_dir_and_version(
    odoo_dir: str | None,
    detected_odoo_dir: Path | None,
    detected_version: str | None,
) -> tuple[Path, str]:
    """Determine odoo_dir path and infer odoo_version from it.

    Priority for odoo_dir: explicit --odoo-dir flag > auto-detected from --project-dir.
    The version is always inferred from the Odoo source (release.py).
    Exits with an error if odoo_dir cannot be resolved or version cannot be detected.
    """
    if odoo_dir:
        odoo_dir_path = Path(odoo_dir).expanduser().resolve()
    elif detected_odoo_dir:
        odoo_dir_path = detected_odoo_dir
    else:
        typer.secho("error: --odoo-dir is required when --project-dir is not used.", fg=typer.colors.RED)
        raise typer.Exit(1)

    # When --odoo-dir is explicit, always infer version from that path
    # (detected_version may come from a different Odoo source via --project-dir).
    if odoo_dir:
        resolved_version = get_odoo_version_from_release(odoo_dir_path)
        # Warn if --project-dir detected a different version than --odoo-dir
        if detected_version and resolved_version and detected_version != resolved_version:
            typer.secho(
                f"error: version mismatch — --project-dir detected '{detected_version}' "
                f"but --odoo-dir contains '{resolved_version}'. "
                "Use the same Odoo source in both or drop one of the flags.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
    else:
        resolved_version = detected_version or get_odoo_version_from_release(odoo_dir_path)

    if not resolved_version:
        typer.secho(
            "error: could not detect Odoo version from source. "
            "Ensure the --odoo-dir path contains a valid Odoo installation.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    return odoo_dir_path, resolved_version


_GITHUB_REPO = "trobz/odoo-venv"


def _create_github_issue(command: str, output: str) -> None:
    """Open a bug report on GitHub via ``gh issue create``."""
    title = f"Error running: `{command}`"
    body = (
        "## Command\n\n"
        f"```\n{command}\n```\n\n"
        "## Output\n\n"
        f"```\n{output}\n```\n\n"
        "*Reported automatically by `--report-errors`.*"
    )
    try:
        result = subprocess.run(  # noqa: S603
            ["gh", "issue", "create", "--repo", _GITHUB_REPO, "--title", title, "--body", body],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        typer.secho(f"Issue created: {url}", fg=typer.colors.GREEN)
    except FileNotFoundError:
        typer.secho("warning: gh CLI not found — could not create GitHub issue.", fg=typer.colors.YELLOW)
    except subprocess.CalledProcessError as exc:
        typer.secho(f"warning: could not create GitHub issue:\n{exc.stderr}", fg=typer.colors.YELLOW)


def _run_with_error_reporting(argv: list[str]) -> None:
    """Re-run *argv* without ``--report-errors``, tee all output, and file a GitHub issue on failure.

    stdout and stderr from the child process are merged so that the full
    terminal output (including uv subprocess output) is captured in one stream
    and printed to the terminal in real time.
    """
    cmd = [a for a in argv if a != "--report-errors"]
    captured: list[str] = []

    proc = subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.stdout is not None  # noqa: S101
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        captured.append(line)
    proc.wait()

    if proc.returncode != 0:
        full_command = " ".join(cmd)
        _create_github_issue(full_command, "".join(captured))

    raise typer.Exit(proc.returncode)


@app.command()
def create(
    ctx: typer.Context,
    python_version: Annotated[
        str | None,
        typer.Option("--python-version", "-p", help="Specify Python version."),
    ] = None,
    venv_dir: Annotated[str, typer.Option(help="Path to create the virtual environment.")] = "./.venv",
    odoo_dir: Annotated[str | None, typer.Option(help="Path to Odoo source code.")] = None,
    addons_path: Annotated[
        str | None,
        typer.Option(help="Comma-separated list of addons paths."),
    ] = None,
    install_odoo: Annotated[
        bool,
        typer.Option(
            help="Install Odoo in editable mode.",
        ),
    ] = True,
    install_odoo_requirements: Annotated[
        bool,
        typer.Option(
            help="Install packages from Odoo's requirement.txt.",
        ),
    ] = True,
    ignore_from_odoo_requirements: Annotated[
        str | None,
        typer.Option(help="Comma-separated list of packages to ignore from Odoo's requirement.txt."),
    ] = None,
    install_addons_dirs_requirements: Annotated[
        bool,
        typer.Option(
            help="Install requirements.txt found in addons paths.",
        ),
    ] = False,
    ignore_from_addons_dirs_requirements: Annotated[
        str | None,
        typer.Option(help="Comma-separated list of packages to ignore from addons paths' requirement.txt."),
    ] = None,
    install_addons_manifests_requirements: Annotated[
        bool,
        typer.Option(
            help="Install requirements from addons' manifests.",
        ),
    ] = False,
    ignore_from_addons_manifests_requirements: Annotated[
        str | None,
        typer.Option(help="Comma-separated list of packages to ignore from addons' manifests."),
    ] = None,
    extra_requirements_file: Annotated[
        str | None,
        typer.Option(
            help="Path to an extra requirements file.",
        ),
    ] = None,
    extra_requirement: Annotated[
        str | None,
        typer.Option(help="Comma-separated list of extra packages to install. Use \\, for a literal comma."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(help="Display more details to user"),
    ] = False,
    skip_on_failure: Annotated[
        bool,
        typer.Option(
            "--skip-on-failure/--no-skip-on-failure",
            help="Automatically skip packages that fail to install and retry.",
        ),
    ] = False,
    preset: Annotated[
        str | None,
        typer.Option(
            "--preset",
            callback=preset_callback,
            is_eager=True,  # tell Typer to process this first
            help="Use a preset of options. Preset values can be overriden by other options.",
        ),
    ] = None,
    create_launcher_flag: Annotated[
        bool,
        typer.Option(
            "--create-launcher/--no-create-launcher",
            help="Generate a launcher script in ~/.local/bin/.",
        ),
    ] = False,
    project_dir: Annotated[
        str | None,
        typer.Option(
            "--project-dir",
            callback=project_dir_callback,
            is_eager=True,
            help="Path to project directory. Auto-detects --addons-path, --odoo-dir "
            "via odoo-addons-path and applies --preset=project.",
        ),
    ] = None,
    from_config: Annotated[
        str | None,
        typer.Option(
            "--from",
            callback=from_config_callback,
            is_eager=True,
            help="Path to a venv dir or .odoo-venv.toml file to recreate from.",
        ),
    ] = None,
    report_errors: Annotated[
        bool,
        typer.Option(
            "--report-errors",
            help="On failure, automatically open a GitHub issue with the full command and output.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing virtual environment."),
    ] = False,
):
    """Create virtual environment to run Odoo"""
    if report_errors:
        _run_with_error_reporting(sys.argv)
        return

    # Auto-detect layout from --project-dir if provided
    project_dir_value = ctx.obj.get("project_dir") if ctx.obj else None
    detected_odoo_dir, detected_version, detected_addons_path = (
        _detect_project_layout(project_dir_value) if project_dir_value else (None, None, None)
    )

    odoo_dir_path, odoo_version = _resolve_odoo_dir_and_version(odoo_dir, detected_odoo_dir, detected_version)

    if not python_version:
        python_version = ODOO_PYTHON_VERSIONS.get(odoo_version)

    venv_dir_path = Path(venv_dir).expanduser().resolve()

    # Merge preset's extra_requirement (stored in ctx.obj) with any explicit CLI value.
    # The CLI value is additive: --extra-requirement="" means "nothing extra beyond the preset".
    extra_requirements_list = _build_extra_requirements(ctx, extra_requirement)

    if not addons_path and detected_addons_path:
        addons_path = detected_addons_path

    addons_path_list = (
        [str(Path(p.strip()).expanduser().resolve()) for p in addons_path.split(",")] if addons_path else None
    )

    # Get extra_commands from preset if available
    extra_commands = ctx.obj.get("extra_commands") if ctx.obj else None

    # Build ignore_sources: map each ignored package to its source tag
    ignore_sources = _build_ignore_sources(
        ctx,
        preset,
        {
            "ignore_from_odoo_requirements": ignore_from_odoo_requirements,
            "ignore_from_addons_dirs_requirements": ignore_from_addons_dirs_requirements,
            "ignore_from_addons_manifests_requirements": ignore_from_addons_manifests_requirements,
        },
    )

    result = create_odoo_venv(
        odoo_version=odoo_version,
        odoo_dir=str(odoo_dir_path),
        venv_dir=str(venv_dir_path),
        python_version=python_version,
        install_odoo=install_odoo,
        install_odoo_requirements=install_odoo_requirements,
        ignore_from_odoo_requirements=ignore_from_odoo_requirements,
        addons_paths=addons_path_list,
        install_addons_dirs_requirements=install_addons_dirs_requirements,
        ignore_from_addons_dirs_requirements=ignore_from_addons_dirs_requirements,
        install_addons_manifests_requirements=install_addons_manifests_requirements,
        ignore_from_addons_manifests_requirements=ignore_from_addons_manifests_requirements,
        extra_requirements_file=extra_requirements_file,
        extra_requirements=extra_requirements_list,
        extra_commands=extra_commands,
        verbose=verbose,
        skip_on_failure=skip_on_failure,
        force=force,
        ignore_sources=ignore_sources,
    )

    if create_launcher_flag:
        create_launcher(odoo_version, venv_dir_path, odoo_dir=odoo_dir_path, force=True)

    effective_preset = preset
    if not effective_preset and project_dir_value:
        effective_preset = "project"
    elif not effective_preset:
        effective_preset = "common"

    config_args = {
        "preset": effective_preset or "",
        "python_version": python_version or "",
        "odoo_dir": str(odoo_dir_path),
        "venv_dir": str(venv_dir_path),
        "addons_path": addons_path or "",
        "install_odoo": install_odoo,
        "install_odoo_requirements": install_odoo_requirements,
        "ignore_from_odoo_requirements": ignore_from_odoo_requirements or "",
        "install_addons_dirs_requirements": install_addons_dirs_requirements,
        "ignore_from_addons_dirs_requirements": ignore_from_addons_dirs_requirements or "",
        "install_addons_manifests_requirements": install_addons_manifests_requirements,
        "ignore_from_addons_manifests_requirements": ignore_from_addons_manifests_requirements or "",
        "extra_requirements_file": extra_requirements_file or "",
        "extra_requirement": ",".join(extra_requirements_list) if extra_requirements_list else "",
        "skip_on_failure": skip_on_failure,
        "create_launcher": create_launcher_flag,
        "project_dir": project_dir_value or "",
    }

    write_venv_config(
        venv_dir_path,
        config_args,
        odoo_version,
        requirements=result.requirements or None,
        ignored=result.ignored or None,
    )


def _is_uv_venv(venv_dir: Path) -> bool:
    """Return True if the venv was created by uv (detected via pyvenv.cfg)."""
    cfg = venv_dir / "pyvenv.cfg"
    try:
        return any(line.startswith("uv =") for line in cfg.read_text().splitlines())
    except OSError:
        return False


def _freeze_venv(venv_dir: Path) -> dict[str, str]:
    """Run ``uv pip freeze`` or ``pip freeze`` on a venv depending on how it was created.

    Returns a ``{normalized_name: version}`` dict.
    Uses the venv's own ``pip`` for venvs not created by uv, because
    ``uv pip freeze`` returns empty output in that case.
    """
    if _is_uv_venv(venv_dir):
        cmd = ["uv", "pip", "freeze", "--python", str(venv_dir)]
    else:
        cmd = [str(venv_dir / "bin" / "pip"), "freeze", "--all"]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603
    pkgs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if "==" in line:
            name, ver = line.split("==", 1)
            pkgs[re.sub(r"[-_.]+", "-", name).lower()] = ver
    return pkgs


SKIP_DIRS = {".git", "node_modules", "__pycache__", ".tox", ".nox", ".mypy_cache", ".ruff_cache"}


def _discover_venvs(root: Path) -> list[Path]:
    venvs: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if VENV_CONFIG_FILENAME in filenames:
            venvs.append(Path(dirpath))
            dirnames.clear()  # don't descend into venv internals
    return sorted(venvs)


def _read_venv_info(venv_dir: Path) -> dict[str, str]:
    """Read display info from ``.odoo-venv.toml``.

    Returns a dict with keys: ``python``, ``odoo``, ``preset``.
    """
    args, metadata, _requirements, _ignored = read_venv_config(venv_dir)
    return {
        "python": str(args.get("python_version", "")) or "N/A",
        "odoo": metadata.get("odoo_version", "") or "N/A",
        "preset": str(args.get("preset", "")),
    }


def _freeze_remote_venv(host: str, remote_path: str) -> dict[str, str]:
    """Run ``pip freeze`` on a remote venv over SSH.

    Returns a ``{normalized_name: version}`` dict.
    Detects uv venvs remotely; falls back to the venv's own pip.
    """
    check = subprocess.run(  # noqa: S603
        ["ssh", host, f"grep -q 'uv =' {remote_path}/pyvenv.cfg 2>/dev/null"],  # noqa: S607
        capture_output=True,
    )
    if check.returncode == 0:
        freeze_cmd = f"uv pip freeze --python {remote_path}"
    else:
        freeze_cmd = f"{remote_path}/bin/pip freeze --all"

    result = subprocess.run(  # noqa: S603
        ["ssh", host, freeze_cmd],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    pkgs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if "==" in line:
            name, ver = line.split("==", 1)
            pkgs[re.sub(r"[-_.]+", "-", name).lower()] = ver
    return pkgs


def _parse_requirements_text(text: str) -> dict[str, str]:
    """Parse pip-freeze-style text into a ``{normalized_name: version}`` dict."""
    pkgs: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "==" in line:
            name, ver = line.split("==", 1)
            pkgs[re.sub(r"[-_.]+", "-", name).lower()] = ver
    return pkgs


def _read_requirements_file(path: Path) -> dict[str, str]:
    """Read a local pip-freeze-style requirements file."""
    return _parse_requirements_text(path.read_text())


def _read_remote_requirements_file(host: str, remote_path: str) -> dict[str, str]:
    """Read a remote pip-freeze-style requirements file over SSH."""
    result = subprocess.run(  # noqa: S603
        ["ssh", host, f"cat {remote_path}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return _parse_requirements_text(result.stdout)


def _detect_remote_kind(host: str, remote_path: str) -> str:
    """Return ``'venv'`` if *remote_path* is a directory, ``'file'`` if it is a regular file.

    Exits with an error if the path does not exist on the remote host.
    """
    shell_cmd = (
        f"if [ -d {remote_path} ]; then echo venv; elif [ -f {remote_path} ]; then echo file; else echo notfound; fi"
    )
    result = subprocess.run(  # noqa: S603
        ["ssh", host, shell_cmd],  # noqa: S607
        capture_output=True,
        text=True,
    )
    kind = result.stdout.strip()
    if kind in ("venv", "file"):
        return kind
    typer.secho(f"error: {host}:{remote_path} does not exist.", fg=typer.colors.RED)
    raise typer.Exit(1)


def _parse_venv_arg(arg: str) -> tuple[str | None, str]:
    """Parse a venv argument into ``(host, path)``.

    - ``/path/to/venv``          -> ``(None, '/path/to/venv')``
    - ``host:path``              -> ``(host, 'path')``
    - ``host:/absolute/path``    -> ``(host, '/absolute/path')``

    A colon separates host from path only when the part before it contains
    no ``/`` (i.e. it looks like a hostname, not an absolute path).
    """
    if ":" in arg:
        host, path = arg.split(":", 1)
        if host and "/" not in host:
            return host, path
    return None, arg


def _fetch_latest_pypi(package: str) -> str:
    """Return the latest version of *package* from PyPI, or ``"?"`` on failure."""
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
            return json.loads(resp.read())["info"]["version"]
    except Exception:
        return "?"


def _build_compare_table(
    labels: list[str],
    all_packages: dict[str, dict[str, str]],
    all_names: list[str],
    latest: dict[str, str],
    show_latest: bool,
):
    from rich import box
    from rich.table import Table

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Package", style="bold", no_wrap=True)
    for label in labels:
        table.add_column(label, justify="center")
    if show_latest:
        table.add_column("Latest", justify="center")

    for name in all_names:
        versions = [all_packages[label].get(name) for label in labels]
        has_diff = len({v for v in versions if v is not None}) > 1

        cells: list[str] = []
        for ver in versions:
            if ver is None:
                cells.append("[dim]-[/dim]")
            elif has_diff:
                cells.append(f"[yellow]{ver}[/yellow]")
            else:
                cells.append(ver)

        row: list[str] = [name, *cells]

        if show_latest:
            lat = latest.get(name, "?")
            is_outdated = lat != "?" and any(ver is not None and ver != lat for ver in versions)
            row.append(f"[red]{lat}[/red]" if is_outdated else f"[green]{lat}[/green]")

        table.add_row(*row)

    return table


def _resolve_venv_args(venv_dirs: list[str]) -> tuple[list[tuple[str | None, str, str]], list[str]]:
    """Parse and validate venv arguments; return ``(parsed, labels)``.

    *parsed* is a list of ``(host, path, kind)`` tuples where *host* is ``None``
    for local entries and *kind* is ``'venv'`` or ``'file'``.
    *labels* are deduplicated display names for table columns.
    """
    parsed: list[tuple[str | None, str, str]] = []
    raw_labels: list[str] = []
    for arg in venv_dirs:
        host, path = _parse_venv_arg(arg)
        if host is None:
            local = Path(path).expanduser().resolve()
            if local.is_dir():
                kind = "venv"
            elif local.is_file():
                kind = "file"
            else:
                typer.secho(f"error: {local} is not a file or directory.", fg=typer.colors.RED)
                raise typer.Exit(1)
            parsed.append((None, str(local), kind))
            raw_labels.append(local.name)
        else:
            kind = _detect_remote_kind(host, path)
            parsed.append((host, path, kind))
            raw_labels.append(f"{host}:{Path(path).name}")

    # Deduplicate labels (append index suffix if two entries share the same basename)
    labels: list[str] = []
    seen: dict[str, int] = {}
    for label in raw_labels:
        if label in seen:
            seen[label] += 1
            labels.append(f"{label}({seen[label]})")
        else:
            seen[label] = 0
            labels.append(label)

    return parsed, labels


def _collect_packages(parsed: list[tuple[str | None, str, str]], labels: list[str]) -> dict[str, dict[str, str]]:
    """Collect packages from each venv or requirements file; return ``{label: packages}``."""
    all_packages: dict[str, dict[str, str]] = {}
    for (host, path, kind), label in zip(parsed, labels, strict=True):
        if kind == "file":
            typer.secho(f"Reading {label}...", fg=typer.colors.CYAN)
            try:
                all_packages[label] = (
                    _read_requirements_file(Path(path)) if host is None else _read_remote_requirements_file(host, path)
                )
            except (OSError, subprocess.CalledProcessError) as exc:
                msg = exc.strerror if isinstance(exc, OSError) else exc.stderr
                typer.secho(f"error: failed to read {label}:\n{msg}", fg=typer.colors.RED)
                raise typer.Exit(1) from exc
        else:
            typer.secho(f"Freezing {label}...", fg=typer.colors.CYAN)
            try:
                all_packages[label] = _freeze_venv(Path(path)) if host is None else _freeze_remote_venv(host, path)
            except subprocess.CalledProcessError as exc:
                typer.secho(f"error: failed to freeze {label}:\n{exc.stderr}", fg=typer.colors.RED)
                raise typer.Exit(1) from exc
    return all_packages


@app.command()
def compare(
    venv_dirs: Annotated[
        list[str],
        typer.Argument(
            help="Venv directories or requirements files to compare. Use host:path for remote entries (SSH)."
        ),
    ],
    no_latest: Annotated[
        bool,
        typer.Option("--no-latest", help="Do not fetch or show the 'Latest' column from PyPI."),
    ] = False,
):
    """Compare installed package versions across virtual environments or requirements files.

    Each argument is a local path or a remote entry in ``host:path`` format (SSH).
    Directories are treated as venvs (frozen with pip/uv); files are read as
    pip-freeze-style requirements (``package==version`` lines).

    Examples::

        odoo-venv compare .venv ~/other-venv
        odoo-venv compare .venv staging-host:~/.venvs/odoo18
        odoo-venv compare .venv staging-host:~/.venvs/odoo18 ~/freeze.txt
    """
    from rich.console import Console

    if not venv_dirs:
        typer.secho("error: at least one venv directory is required.", fg=typer.colors.RED)
        raise typer.Exit(1)

    parsed, labels = _resolve_venv_args(venv_dirs)
    all_packages = _collect_packages(parsed, labels)

    all_names = sorted({name for pkgs in all_packages.values() for name in pkgs})

    # Fetch latest versions in parallel
    latest: dict[str, str] = {}
    if not no_latest:
        typer.secho("Fetching latest versions from PyPI...", fg=typer.colors.CYAN)
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(_fetch_latest_pypi, name): name for name in all_names}
            for fut in concurrent.futures.as_completed(futures):
                latest[futures[fut]] = fut.result()

    table = _build_compare_table(labels, all_packages, all_names, latest, show_latest=not no_latest)
    Console().print(table)


@app.command()
def activate(
    venv_dir: Annotated[str, typer.Option(help="Path to virtual environment.")] = "./.venv",
):
    """Activate a virtual environment (spawns a new shell)."""
    from odoo_venv.activate import activate_venv

    venv_path = Path(venv_dir).expanduser().resolve()
    if not (venv_path / "bin" / "activate").is_file():
        typer.secho(f"error: no venv found at {venv_path}", fg=typer.colors.RED)
        raise typer.Exit(1)

    activate_venv(venv_path)


@app.command()
def create_odoo_launcher(
    odoo_version: Annotated[str, typer.Argument(help="Odoo version, e.g: 19.0 or master")],
    venv_dir: Annotated[str, typer.Option(help="Path to the virtual environment.")],
    odoo_dir: Annotated[
        str | None, typer.Option(help="Path to Odoo source (required for non-numeric versions like 'master').")
    ] = None,
    force: Annotated[bool, typer.Option(help="Overwrite existing launcher script.")] = False,
):
    """Generate a launcher script in ~/.local/bin/ for the Odoo environment"""
    venv_dir_path = Path(venv_dir).expanduser().resolve()
    odoo_dir_path = Path(odoo_dir).expanduser().resolve() if odoo_dir else None
    create_launcher(odoo_version, venv_dir_path, odoo_dir=odoo_dir_path, force=force)


def _build_update_venv(merged: dict, odoo_version: str, tmp_venv_path: Path):
    """Create a temporary venv from merged config. Returns VenvResult."""
    # Resolve preset's extra_commands if a preset is set
    extra_commands = None
    merged_preset = merged.get("preset")
    if merged_preset:
        all_presets = load_presets()
        if merged_preset in all_presets:
            extra_commands = asdict(all_presets[merged_preset]).get("extra_commands")

    # Build addons_paths list
    addons_path_value = merged.get("addons_path", "")
    addons_paths_list = (
        [str(Path(p.strip()).expanduser().resolve()) for p in addons_path_value.split(",")]
        if addons_path_value
        else None
    )

    # Build extra_requirements list
    extra_req_str = merged.get("extra_requirement", "")
    extra_requirements_list = split_escaped(extra_req_str) if extra_req_str else []

    # Build ignore_sources from stored config — check which ignores come from the preset
    ignore_sources = _build_ignore_sources_from_config(merged)

    return create_odoo_venv(
        odoo_version=odoo_version,
        odoo_dir=merged.get("odoo_dir", ""),
        venv_dir=str(tmp_venv_path),
        python_version=merged.get("python_version") or None,
        install_odoo=merged.get("install_odoo", True),
        install_odoo_requirements=merged.get("install_odoo_requirements", True),
        ignore_from_odoo_requirements=merged.get("ignore_from_odoo_requirements") or None,
        addons_paths=addons_paths_list,
        install_addons_dirs_requirements=merged.get("install_addons_dirs_requirements", False),
        ignore_from_addons_dirs_requirements=merged.get("ignore_from_addons_dirs_requirements") or None,
        install_addons_manifests_requirements=merged.get("install_addons_manifests_requirements", False),
        ignore_from_addons_manifests_requirements=merged.get("ignore_from_addons_manifests_requirements") or None,
        extra_requirements_file=merged.get("extra_requirements_file") or None,
        extra_requirements=extra_requirements_list or None,
        extra_commands=extra_commands,
        verbose=False,
        skip_on_failure=merged.get("skip_on_failure", False),
        ignore_sources=ignore_sources,
    )


def _swap_venvs(venv_path: Path, tmp_venv_path: Path, *, backup: bool) -> None:
    """Atomically replace *venv_path* with *tmp_venv_path*."""

    if backup:
        bak_path = venv_path.parent / f"{venv_path.name}.bak"
        if bak_path.exists():
            shutil.rmtree(bak_path)
        venv_path.rename(bak_path)
        typer.secho(f"Backed up to {bak_path}", fg=typer.colors.CYAN)
    else:
        shutil.rmtree(venv_path)

    tmp_venv_path.rename(venv_path)


@app.command()
def update(
    venv_dir: Annotated[str, typer.Argument(help="Path to existing venv to update.")],
    backup: Annotated[
        bool,
        typer.Option("--backup/--no-backup", help="Keep old venv as <venv>.bak."),
    ] = True,
    yes: Annotated[
        bool,
        typer.Option(help="Skip confirmation prompt.", is_flag=True),
    ] = False,
):
    """Update an existing venv by rebuilding from its .odoo-venv.toml configuration."""

    venv_path = Path(venv_dir).expanduser().resolve()
    if not venv_path.is_dir():
        typer.secho(f"error: {venv_path} is not a directory.", fg=typer.colors.RED)
        raise typer.Exit(1)

    config_file = venv_path / VENV_CONFIG_FILENAME
    if not config_file.exists():
        typer.secho(
            f"error: {config_file} not found.\nRe-create it with: odoo-venv create ...",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    toml_args, meta, _reqs, _ignored = read_venv_config(venv_path)
    odoo_version_val = meta.get("odoo_version", "")

    # Create tmp venv
    tmp_venv_path = venv_path.parent / f"{venv_path.name}.tmp"
    if tmp_venv_path.exists():
        shutil.rmtree(tmp_venv_path)

    typer.secho(f"Creating temporary venv at {tmp_venv_path}...", fg=typer.colors.CYAN)

    swapped = False
    try:
        result = _build_update_venv(toml_args, odoo_version_val, tmp_venv_path)

        # Write fresh config with updated origin tracking data
        write_venv_config(
            tmp_venv_path,
            toml_args,
            odoo_version_val,
            requirements=result.requirements or None,
            ignored=result.ignored or None,
        )

        typer.secho("\nComparing packages...", fg=typer.colors.CYAN)
        old_pkgs = _freeze_venv(venv_path)
        new_pkgs = _freeze_venv(tmp_venv_path)

        all_names = sorted({*old_pkgs, *new_pkgs})
        all_packages = {"current": old_pkgs, "updated": new_pkgs}
        table = _build_compare_table(
            labels=["current", "updated"],
            all_packages=all_packages,
            all_names=all_names,
            latest={},
            show_latest=False,
        )
        Console().print(table)

        added = sum(1 for n in all_names if n not in old_pkgs)
        removed = sum(1 for n in all_names if n not in new_pkgs)
        changed = sum(1 for n in all_names if n in old_pkgs and n in new_pkgs and old_pkgs[n] != new_pkgs[n])
        typer.secho(f"\n{added} added, {removed} removed, {changed} changed", fg=typer.colors.CYAN)

        confirm = yes or typer.confirm("Apply update?", default=False)
        if not confirm:
            typer.secho("Update cancelled.", fg=typer.colors.YELLOW)
            raise typer.Exit(0)

        _swap_venvs(venv_path, tmp_venv_path, backup=backup)
        swapped = True
        typer.secho("Update complete.", fg=typer.colors.GREEN)
    finally:
        # Clean up tmp venv
        if not swapped and tmp_venv_path.exists():
            shutil.rmtree(tmp_venv_path)


def _origin_label(origin: str) -> str:
    """Return a short human-readable label for a requirement origin tag."""
    if origin == "odoo":
        return "Odoo requirements.txt"
    if origin == "extra_requirement":
        return "Extra requirement"
    if origin == "transitive":
        return "Transitive"
    if origin == "build_tool":
        return "Build tool"
    if origin == "no_build_isolation":
        return "No-build-isolation"
    if origin.startswith("addons_dir:"):
        return f"Addons dir: {origin[len('addons_dir:') :]}"
    if origin.startswith("manifest:"):
        return f"Addon manifest: {origin[len('manifest:') :]}"
    if origin.startswith("extra_requirements_file:"):
        return f"Extra file: {origin[len('extra_requirements_file:') :]}"
    return origin


def _ignored_reason_label(reason: str) -> str:
    """Return a short human-readable label for an ignored reason tag."""
    if reason == "explicit_ignore":
        return "Explicitly ignored"
    if reason.startswith("explicit_ignore:preset:"):
        # Format: explicit_ignore:preset:<name>:<flag>
        parts = reason.split(":", 3)  # ["explicit_ignore", "preset", "<name>", "<flag>"]
        preset_name = parts[2] if len(parts) > 2 else "?"
        cli_flag = parts[3] if len(parts) > 3 else ""
        return f'Preset "{preset_name}" ({cli_flag})' if cli_flag else f'Preset "{preset_name}"'
    if reason.startswith("explicit_ignore:"):
        # Format: explicit_ignore:<flag>
        cli_flag = reason[len("explicit_ignore:") :]
        return cli_flag
    if reason == "auto_override":
        return "Overridden by user constraint"
    if reason.startswith("auto_override:"):
        source = reason[len("auto_override:") :]
        return f"Overridden by {source}"
    if reason == "install_failure":
        return "Install failure (skip-on-failure)"
    if reason.startswith("transitive_conflict:"):
        return f"Transitive conflict with {reason[len('transitive_conflict:') :]}"
    return reason


_ORIGIN_ORDER = [
    "odoo",
    "addons_dir:",
    "manifest:",
    "extra_requirement",
    "extra_requirements_file:",
    "no_build_isolation",
    "build_tool",
    "transitive",
]


def _origin_sort_key(origin: str) -> int:
    for i, prefix in enumerate(_ORIGIN_ORDER):
        if origin == prefix or origin.startswith(prefix):
            return i
    return len(_ORIGIN_ORDER)


def _group_requirements(
    requirements: dict[str, list[str]], no_transitive: bool
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Group packages by origin and collect transitive children for tree rendering.

    Returns ``(groups, transitive_children)`` where *groups* maps origin keys to
    package lists and *transitive_children* maps parent packages to their transitive deps.
    """
    transitive_children: dict[str, list[str]] = {}
    transitive_with_parent: set[str] = set()

    groups: dict[str, list[str]] = {}
    for pkg, origins in requirements.items():
        is_transitive = all(o.startswith("transitive") for o in origins)
        if no_transitive and is_transitive:
            continue
        if is_transitive:
            parents = [o[len("transitive:") :] for o in origins if o.startswith("transitive:")]
            if parents:
                transitive_with_parent.add(pkg)
                for parent in parents:
                    transitive_children.setdefault(parent, []).append(pkg)
                continue
        primary = min(origins, key=_origin_sort_key)
        groups.setdefault(primary, []).append(pkg)

    # Orphaned transitive deps (parent not rendered anywhere) → flat "Transitive" group
    rendered_pkgs = {pkg for pkgs in groups.values() for pkg in pkgs}
    rendered_pkgs |= {child for children in transitive_children.values() for child in children}
    for pkg in sorted(transitive_with_parent):
        parents = [o[len("transitive:") :] for o in requirements[pkg] if o.startswith("transitive:")]
        if not any(p in rendered_pkgs for p in parents):
            groups.setdefault("transitive", []).append(pkg)

    return groups, transitive_children


def _build_pkg_lines(pkg: str, transitive_children: dict[str, list[str]], indent: str = "") -> list[str]:
    """Build display lines for a package and its transitive children (recursive)."""
    lines = [f"[cyan]{pkg}[/cyan]" if not indent else f"[dim]{indent}{pkg}[/dim]"]
    children = sorted(transitive_children.get(pkg, []))
    for i, child in enumerate(children):
        is_last = i == len(children) - 1
        prefix = "└── " if is_last else "├── "
        continuation = "    " if is_last else "│   "
        lines.append(f"[dim]{indent}{prefix}{child}[/dim]")
        # Add grandchildren with proper indentation
        grandchildren = sorted(transitive_children.get(child, []))
        for j, grandchild in enumerate(grandchildren):
            gc_prefix = "└── " if j == len(grandchildren) - 1 else "├── "
            lines.append(f"[dim]{indent}{continuation}{gc_prefix}{grandchild}[/dim]")
    return lines


def _render_blocks_as_table(blocks: list[list[str]]):
    """Render a list of markup-line blocks into a single Rich Table."""
    from rich import box
    from rich.table import Table
    from rich.text import Text

    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column("Package", no_wrap=True)
    for block in blocks:
        for line in block:
            t.add_row(Text.from_markup(line))
    return t


def _render_multicolumn(blocks: list[list[str]]):
    """Distribute blocks across balanced columns and return a Rich Columns renderable."""
    import math

    from rich.columns import Columns

    total_lines = sum(len(b) for b in blocks)
    num_cols = min(3, math.ceil(total_lines / 20))
    target_lines = math.ceil(total_lines / num_cols)
    columns_blocks: list[list[list[str]]] = [[]]
    current_lines = 0
    for block in blocks:
        if current_lines > 0 and current_lines + len(block) > target_lines and len(columns_blocks) < num_cols:
            columns_blocks.append([])
            current_lines = 0
        columns_blocks[-1].append(block)
        current_lines += len(block)
    return Columns([_render_blocks_as_table(cb) for cb in columns_blocks], padding=(0, 2))


def _print_requirements_panels(console, requirements: dict[str, list[str]], no_transitive: bool) -> None:
    from rich.panel import Panel

    if not requirements:
        console.print("\n[dim]No requirement origin data available. Re-create the venv to populate it.[/dim]")
        return

    groups, transitive_children = _group_requirements(requirements, no_transitive)

    console.print()
    for origin in sorted(groups.keys(), key=_origin_sort_key):
        pkgs = sorted(groups[origin])
        label = _origin_label(origin)

        blocks: list[list[str]] = [_build_pkg_lines(pkg, transitive_children) for pkg in pkgs]
        total_lines = sum(len(b) for b in blocks)
        content = (
            _render_multicolumn(blocks) if len(pkgs) > 10 and total_lines > 15 else _render_blocks_as_table(blocks)
        )
        console.print(Panel(content, title=f"[bold green]{label}[/bold green] ({len(pkgs)})", expand=False))


def _print_ignored_panel(console, ignored: dict[str, list[str]]) -> None:
    from rich import box
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold yellow")
    table.add_column("Package", style="bold", no_wrap=True)
    table.add_column("Reason")
    for pkg in sorted(ignored.keys()):
        reasons = ", ".join(_ignored_reason_label(r) for r in ignored[pkg])
        table.add_row(pkg, Text(reasons, style="yellow"))
    console.print(Panel(table, title="[bold yellow]Ignored Packages[/bold yellow]", expand=False))


@app.command()
def show(
    venv_dir: Annotated[str, typer.Argument(help="Path to the venv directory.")] = "./.venv",
    no_transitive: Annotated[
        bool,
        typer.Option("--no-transitive", help="Hide transitive dependencies."),
    ] = False,
):
    """Show the configuration and installed packages of a venv."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    venv_path = Path(venv_dir).expanduser().resolve()

    try:
        args, meta, requirements, ignored = read_venv_config(venv_path)
    except FileNotFoundError:
        typer.secho(
            f"error: no .odoo-venv.toml found in {venv_path}\nCreate a venv first with: odoo-venv create ...",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1) from None

    # --- Config panel ---
    odoo_version = meta.get("odoo_version", "unknown")
    tool_version = meta.get("tool_version", "unknown")
    config_lines = [
        f"[bold]Venv:[/bold]          {venv_path}",
        f"[bold]Odoo version:[/bold]  {odoo_version}",
        f"[bold]Tool version:[/bold]  {tool_version}",
    ]
    for key, label in [("preset", "Preset"), ("python_version", "Python"), ("odoo_dir", "Odoo dir")]:
        if val := args.get(key):
            config_lines.append(f"[bold]{label + ':':<14}[/bold] {val}")
    console.print(Panel("\n".join(config_lines), title="[bold cyan]Venv Configuration[/bold cyan]", expand=False))

    _print_requirements_panels(console, requirements, no_transitive)

    if ignored:
        console.print()
        _print_ignored_panel(console, ignored)


@app.command("list")
def list_venvs():
    """List virtual environments found under the current directory."""

    root = Path.cwd()
    venvs = _discover_venvs(root)

    if not venvs:
        typer.secho("No virtual environments found.", fg=typer.colors.YELLOW)
        raise typer.Exit(0)

    table = Table(show_header=True, header_style="bold")
    table.add_column("PATH")
    table.add_column("PYTHON")
    table.add_column("ODOO")
    table.add_column("PRESET")

    for venv_dir in venvs:
        rel_path = f"./{venv_dir.relative_to(root)}"
        info = _read_venv_info(venv_dir)
        table.add_row(rel_path, info["python"], info["odoo"], info["preset"])

    Console().print(table)
