"""Orchestrator and DB lifecycle for the ovx command."""

import ast
import contextlib
import re
import shutil
import signal
import subprocess
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

import typer
from odoo_addons_path import get_addons_path, get_odoo_version_from_release

from odoo_venv.exceptions import (
    ConflictingOdooSeriesError,
    OdooSeriesUndeterminedError,
    OdooVersionUndeterminedError,
    ResolvedVenvPathMissingError,
    VenvCreationRequiresOdooDirError,
)
from odoo_venv.launcher import create_launcher
from odoo_venv.main import create_and_register_venv, resolve_common_preset
from odoo_venv.ovx_resolver import (
    ResolvedVenv,
    clone_venv,
    get_addon_series,
    install_missing_python_deps,
    read_venv_meta,
    resolve_base_venv,
)
from odoo_venv.utils import read_venv_config, split_escaped


def user_supplied_db(extra_args: list[str]) -> bool:
    """Return True if the user passed -d / --database in extra_args."""
    for arg in extra_args:
        if arg in ("-d", "--database"):
            return True
        if arg.startswith("--database="):
            return True
    return False


def build_odoo_argv(
    venv: Path,
    addon_paths: list[Path],
    addons_path: list[str],
    db_name: str,
    extra_args: list[str],
) -> list[str]:
    """Build the Odoo subprocess argv list."""
    modules = ",".join(p.name for p in addon_paths)
    joined = ",".join(addons_path) if addons_path else str(addon_paths[0].parent)
    return [
        str(venv / "bin" / "python"),
        "-m",
        "odoo",
        "-i",
        modules,
        "--addons-path",
        joined,
        "-d",
        db_name,
        *extra_args,
    ]


def make_ephemeral_db_name(names: list[str]) -> str:
    """Generate a unique ephemeral DB name from addon directory names."""
    sanitized_parts = [re.sub(r"[^a-z0-9_]", "_", n.lower()) for n in names]
    joined = "_".join(sanitized_parts)[:50]
    suffix = uuid.uuid4().hex[:8]
    return f"ovx_{joined}_{suffix}"


def _drop_db(name: str) -> None:
    """Drop a Postgres database by name, silently ignoring failures."""
    result = subprocess.run(  # noqa: S603
        ["dropdb", "--if-exists", name],  # noqa: S607
        capture_output=True,
    )
    if result.returncode != 0:
        subprocess.run(  # noqa: S603
            ["psql", "-c", f'DROP DATABASE IF EXISTS "{name}";', "postgres"],  # noqa: S607
            capture_output=True,
        )


def run_with_db_lifecycle(odoo_cmd: list[str], db_name: str | None) -> int:
    """Spawn Odoo and manage ephemeral DB cleanup.

    If *db_name* is not None, the DB is dropped after Odoo exits (success or failure).
    If *db_name* is None, the caller manages the DB lifecycle (user-supplied -d).
    """
    managed = db_name is not None
    proc = subprocess.Popen(odoo_cmd)  # noqa: S603

    old_sigint = signal.getsignal(signal.SIGINT)
    old_sigterm = signal.getsignal(signal.SIGTERM)

    def _forward(sig, _frame):
        with contextlib.suppress(ProcessLookupError):
            proc.send_signal(sig)

    signal.signal(signal.SIGINT, _forward)
    signal.signal(signal.SIGTERM, _forward)

    try:
        rc = proc.wait()
    finally:
        signal.signal(signal.SIGINT, old_sigint)
        signal.signal(signal.SIGTERM, old_sigterm)
        if managed and db_name is not None:
            _drop_db(db_name)

    return rc


def _prepare_target(
    resolved: ResolvedVenv,
    addon_paths: list[Path],
    series: str,
    odoo_dir: Path | None,
    keep_clone: bool,
    extra_addons_paths: list[str] | None = None,
) -> tuple[Path, "Callable[[], None] | None"]:
    """Create or clone the working venv. Returns (target_path, cleanup_fn)."""
    if resolved.fresh:
        # _resolve_series already raised VenvCreationRequiresOdooDirError above if odoo_dir
        # were None here, so this holds by construction.
        assert odoo_dir is not None  # noqa: S101
        if keep_clone:
            clone_dir = Path(tempfile.mkdtemp(prefix="ovx_fresh_"))
            cleanup = None
        else:
            td = tempfile.TemporaryDirectory(prefix="ovx_fresh_")
            clone_dir = Path(td.name)
            cleanup = td.cleanup

        target = clone_dir / f"odoo-{series}-venv"
        typer.secho(f"Creating fresh venv at {target}...", fg=typer.colors.CYAN)
        all_parents = list(dict.fromkeys([*(extra_addons_paths or []), *[str(p.parent) for p in addon_paths]]))

        preset = resolve_common_preset()
        install_odoo = preset.install_odoo if preset and preset.install_odoo is not None else True
        install_odoo_requirements = (
            preset.install_odoo_requirements if preset and preset.install_odoo_requirements is not None else True
        )
        ignore_from_odoo_requirements = preset.ignore_from_odoo_requirements if preset else None
        install_addons_dirs_requirements = bool(preset and preset.install_addons_dirs_requirements)
        ignore_from_addons_dirs_requirements = preset.ignore_from_addons_dirs_requirements if preset else None
        ignore_from_addons_manifests_requirements = preset.ignore_from_addons_manifests_requirements if preset else None
        extra_requirements_file = preset.extra_requirements_file if preset else None
        extra_requirement = preset.extra_requirement if preset else None
        extra_commands = preset.extra_commands if preset else None
        extra_requirements_list = split_escaped(extra_requirement) if extra_requirement else None

        config_args: dict[str, str | bool] = {
            "preset": "common" if preset else "",
            "python_version": "",
            "odoo_dir": str(odoo_dir),
            "venv_dir": str(target),
            "addons_path": ",".join(all_parents),
            "install_odoo": install_odoo,
            "install_odoo_requirements": install_odoo_requirements,
            "ignore_from_odoo_requirements": ignore_from_odoo_requirements or "",
            "install_addons_dirs_requirements": install_addons_dirs_requirements,
            "ignore_from_addons_dirs_requirements": ignore_from_addons_dirs_requirements or "",
            "install_addons_manifests_requirements": True,
            "ignore_from_addons_manifests_requirements": ignore_from_addons_manifests_requirements or "",
            "extra_requirements_file": extra_requirements_file or "",
            "extra_requirement": extra_requirement or "",
            "skip_on_failure": False,
            "create_launcher": False,
            "project_dir": "",
        }

        create_and_register_venv(
            odoo_version=series,
            odoo_dir=str(odoo_dir),
            venv_dir=str(target),
            config_args=config_args,
            python_version=None,
            install_odoo=install_odoo,
            install_odoo_requirements=install_odoo_requirements,
            ignore_from_odoo_requirements=ignore_from_odoo_requirements,
            addons_paths=all_parents,
            install_addons_dirs_requirements=install_addons_dirs_requirements,
            ignore_from_addons_dirs_requirements=ignore_from_addons_dirs_requirements,
            install_addons_manifests_requirements=True,
            ignore_from_addons_manifests_requirements=ignore_from_addons_manifests_requirements,
            extra_requirements_file=extra_requirements_file,
            extra_requirements=extra_requirements_list,
            extra_commands=extra_commands,
            create_launcher_flag=False,
        )
        return target, cleanup

    if resolved.path is None:
        raise ResolvedVenvPathMissingError

    if keep_clone:
        clone_dir = Path(tempfile.mkdtemp(prefix="ovx_clone_"))
        target = clone_dir / resolved.path.name
        shutil.copytree(resolved.path, target, symlinks=True)
        return target, None

    target, cleanup = clone_venv(resolved.path)
    return target, cleanup


def _resolve_series(
    addon_paths: list[Path],
    *,
    odoo_dir: Path | None,
    venv_dir: Path | None,
    venv_meta: dict[str, str] | None,
) -> str:
    """Collect every known Odoo series (flags + addon manifests) and fail on any disagreement."""
    participants: list[tuple[str, str | None]] = []

    if odoo_dir is not None:
        version = get_odoo_version_from_release(odoo_dir)
        if version is None:
            raise OdooVersionUndeterminedError(odoo_dir)
        participants.append((f"--odoo-dir {odoo_dir}", version))

    if venv_dir is not None:
        if venv_meta is None:
            if odoo_dir is None:
                raise VenvCreationRequiresOdooDirError(venv_dir)
        else:
            version = venv_meta.get("odoo_version") or None
            participants.append((f"--venv-dir {venv_dir}", version))

    for addon in addon_paths:
        participants.append((str(addon), get_addon_series(addon)))

    known = {s for _, s in participants if s is not None}

    if len(known) > 1:
        raise ConflictingOdooSeriesError(participants)

    if not known:
        raise OdooSeriesUndeterminedError

    return known.pop()


def run_ovx(
    addon_paths: list[Path],
    *,
    venv_dir: Path | None,
    odoo_dir: Path | None,
    database: str | None,
    keep_clone: bool,
    no_launcher: bool,
    extra_args: list[str],
    addons_path: list[str] | None = None,
) -> int:
    """Main ovx orchestrator. Returns Odoo's exit code."""
    addon_paths = [p.expanduser().resolve() for p in addon_paths]
    extra_addons = addons_path or []

    venv_meta = read_venv_meta(venv_dir) if venv_dir is not None and venv_dir.exists() else None
    series = _resolve_series(addon_paths, odoo_dir=odoo_dir, venv_dir=venv_dir, venv_meta=venv_meta)

    resolved = resolve_base_venv(venv_dir=venv_dir, odoo_dir=odoo_dir)

    target, cleanup = _prepare_target(resolved, addon_paths, series, odoo_dir, keep_clone, extra_addons)
    try:
        if not resolved.fresh:
            all_python_deps: list[str] = []
            seen: set[str] = set()
            for p in addon_paths:
                manifest = ast.literal_eval((p / "__manifest__.py").read_text())
                for dep in manifest.get("external_dependencies", {}).get("python", []):
                    if dep not in seen:
                        seen.add(dep)
                        all_python_deps.append(dep)
            union_manifest = {"external_dependencies": {"python": all_python_deps}}
            missing = install_missing_python_deps(target, union_manifest)
            if missing:
                typer.secho(f"Installed missing deps: {', '.join(missing)}", fg=typer.colors.CYAN)

        if not no_launcher:
            create_launcher(series, target, odoo_dir=odoo_dir, force=False)

        addons_path_parts = _resolve_addons_path(target, addon_paths, extra_addons, odoo_dir=odoo_dir)

        db_name_managed, argv = _build_db_and_argv(target, addon_paths, addons_path_parts, database, extra_args)

        if keep_clone:
            typer.secho(f"Clone kept at: {target}", fg=typer.colors.YELLOW)

        return run_with_db_lifecycle(argv, db_name_managed)

    finally:
        if cleanup and not keep_clone:
            cleanup()


def _resolve_addons_path(
    base: Path | None,
    addon_paths: list[Path],
    extra: list[str] | None = None,
    *,
    odoo_dir: Path | None = None,
) -> list[str]:
    """Build the --addons-path list by delegating to odoo_addons_path.get_addons_path.

    Merges the base venv's recorded `addons_path`, `--addons-path` entries, and each addon's
    parent directory, then resolves them with `codebase=None` so the process CWD can never
    leak into the result. An explicit `--odoo-dir` overrides the venv's recorded `odoo_dir`.
    """
    stored: list[str] = []
    config_odoo_dir: Path | None = None
    if base is not None:
        with contextlib.suppress(FileNotFoundError):
            args, _, _, _ = read_venv_config(base)
            stored_val = args.get("addons_path", "")
            if stored_val:
                stored = [p for p in str(stored_val).split(",") if p]
            odoo_dir_str = args.get("odoo_dir", "")
            if odoo_dir_str and isinstance(odoo_dir_str, str):
                config_odoo_dir = Path(odoo_dir_str)

    effective_odoo_dir = odoo_dir or config_odoo_dir
    addons_dirs = [Path(p) for p in stored] + [Path(p) for p in (extra or [])] + [p.parent for p in addon_paths]

    result = get_addons_path(codebase=None, addons_dir=addons_dirs, odoo_dir=effective_odoo_dir)
    return [p for p in result.split(",") if p]


def _build_db_and_argv(
    target: Path,
    addon_paths: list[Path],
    addons_path_parts: list[str],
    database: str | None,
    extra_args: list[str],
) -> tuple["str | None", list[str]]:
    """Determine DB name and build the Odoo argv. Returns (managed_db_name, argv)."""
    if user_supplied_db(extra_args):
        db_for_argv = _extract_db_from_args(extra_args) or "odoo"
        return None, build_odoo_argv(target, addon_paths, addons_path_parts, db_for_argv, extra_args)

    if database:
        return None, build_odoo_argv(target, addon_paths, addons_path_parts, database, extra_args)

    db_name = make_ephemeral_db_name([p.name for p in addon_paths])
    return db_name, build_odoo_argv(target, addon_paths, addons_path_parts, db_name, extra_args)


def _extract_db_from_args(extra_args: list[str]) -> str | None:
    """Extract the -d / --database value from extra_args if present."""
    for i, arg in enumerate(extra_args):
        if arg in ("-d", "--database") and i + 1 < len(extra_args):
            return extra_args[i + 1]
        if arg.startswith("--database="):
            return arg.split("=", 1)[1]
    return None
