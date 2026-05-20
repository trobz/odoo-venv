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

from odoo_venv.exceptions import OdooVenvError
from odoo_venv.launcher import create_launcher
from odoo_venv.main import create_odoo_venv
from odoo_venv.ovx_resolver import (
    ResolvedVenv,
    clone_venv,
    get_addon_series,
    install_missing_python_deps,
    resolve_base_venv,
)
from odoo_venv.utils import read_venv_config


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
        if odoo_dir is None:
            raise OdooVenvError("--odoo-dir is required to create a fresh venv")  # noqa: TRY003
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
        create_odoo_venv(
            odoo_version=series,
            odoo_dir=odoo_dir,
            venv_dir=target,
            python_version=None,
            install_addons_manifests_requirements=True,
            addons_paths=all_parents,
        )
        return target, cleanup

    if resolved.path is None:
        raise OdooVenvError("Internal error: resolved venv path is None")  # noqa: TRY003

    if keep_clone:
        clone_dir = Path(tempfile.mkdtemp(prefix="ovx_clone_"))
        target = clone_dir / resolved.path.name
        shutil.copytree(resolved.path, target, symlinks=True)
        return target, None

    target, cleanup = clone_venv(resolved.path)
    return target, cleanup


def run_ovx(
    addon_paths: list[Path],
    *,
    venv_dir: Path | None,
    odoo_dir: Path | None,
    database: str | None,
    keep_clone: bool,
    no_launcher: bool,
    extra_args: list[str],
    cwd: Path,
    addons_path: list[str] | None = None,
) -> int:
    """Main ovx orchestrator. Returns Odoo's exit code."""
    addon_paths = [p.expanduser().resolve() for p in addon_paths]
    extra_addons = addons_path or []

    series = get_addon_series(addon_paths[0])
    for p in addon_paths[1:]:
        get_addon_series(p)

    resolved = resolve_base_venv(series, venv_dir=venv_dir, cwd=cwd, odoo_dir=odoo_dir)

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

        addons_path_parts = _resolve_addons_path(resolved, addon_paths, extra_addons)

        db_name_managed, argv = _build_db_and_argv(target, addon_paths, addons_path_parts, database, extra_args)

        if keep_clone:
            typer.secho(f"Clone kept at: {target}", fg=typer.colors.YELLOW)

        return run_with_db_lifecycle(argv, db_name_managed)

    finally:
        if cleanup and not keep_clone:
            cleanup()


def _resolve_addons_path(
    resolved: ResolvedVenv,
    addon_paths: list[Path],
    extra: list[str] | None = None,
) -> list[str]:
    """Build the --addons-path list: venv config → extra → each addon's parent, deduped."""
    parts: list[str] = []
    if not resolved.fresh and resolved.path is not None:
        with contextlib.suppress(FileNotFoundError):
            args, _, _, _ = read_venv_config(resolved.path)
            stored = args.get("addons_path", "")
            if stored:
                parts = [p for p in str(stored).split(",") if p]
    parts = parts + (extra or []) + [str(p.parent) for p in addon_paths]
    return list(dict.fromkeys(parts))


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
