"""Venv resolution and clone primitives for the ovx command."""

import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from odoo_addons_path import get_odoo_version_from_addons

from odoo_venv.cli.main import _discover_venvs, _freeze_venv
from odoo_venv.exceptions import OdooVenvError
from odoo_venv.utils import read_venv_config


@dataclass
class ResolvedVenv:
    path: Path | None
    fresh: bool
    source: Literal["explicit", "discovered", "fresh"]


def get_addon_series(addon_path: Path) -> str:
    """Return the Odoo major series (e.g. '19.0') for the given addon directory."""
    if not addon_path.is_dir():
        raise OdooVenvError(f"Addon path is not a directory: {addon_path}")  # noqa: TRY003
    if not (addon_path / "__manifest__.py").is_file():
        raise OdooVenvError(f"Missing __manifest__.py in {addon_path}")  # noqa: TRY003
    series = get_odoo_version_from_addons(str(addon_path.parent))
    if not series:
        raise OdooVenvError(  # noqa: TRY003
            f"Could not determine Odoo series from {addon_path}/__manifest__.py "
            f"(version must be in form 'X.Y.Z.A.B', e.g. '19.0.1.0.0')"
        )
    return series


def resolve_base_venv(
    manifest_series: str,
    *,
    venv_dir: Path | None,
    cwd: Path,
    odoo_dir: Path | None,
) -> ResolvedVenv:
    """Resolve the base venv to use for an ovx run.

    Priority:
      1. Explicit --venv-dir (must exist and version-match)
      2. Auto-discover from cwd (exactly one match)
      3. Fresh-create signal (requires --odoo-dir)
    """
    if venv_dir is not None:
        _, meta, _, _ = read_venv_config(venv_dir)
        found_version = meta.get("odoo_version", "")
        if found_version != manifest_series:
            raise OdooVenvError(  # noqa: TRY003
                f"Venv at {venv_dir} is for Odoo {found_version}, "
                f"but addon requires {manifest_series}. "
                f"Pass a matching --venv-dir or omit it for auto-discovery."
            )
        return ResolvedVenv(path=venv_dir, fresh=False, source="explicit")

    discovered = _discover_venvs(cwd)
    matches = []
    for venv in discovered:
        try:
            _, meta, _, _ = read_venv_config(venv)
        except FileNotFoundError:
            continue
        if meta.get("odoo_version", "") == manifest_series:
            matches.append(venv)

    if len(matches) == 1:
        return ResolvedVenv(path=matches[0], fresh=False, source="discovered")

    if len(matches) > 1:
        paths = ", ".join(str(m) for m in matches)
        raise OdooVenvError(  # noqa: TRY003
            f"Found {len(matches)} venvs for Odoo {manifest_series} ({paths}). Pass --venv-dir to disambiguate."
        )

    # Zero matches
    if odoo_dir is None:
        raise OdooVenvError(  # noqa: TRY003
            f"No venv found for Odoo {manifest_series} in {cwd}. "
            f"Pass --odoo-dir to create a fresh venv, or --venv-dir to specify one."
        )
    return ResolvedVenv(path=None, fresh=True, source="fresh")


def clone_venv(base: Path) -> tuple[Path, "Callable[[], None]"]:
    """Clone *base* venv into a temporary directory.

    Returns ``(clone_path, cleanup_fn)``. The caller must call ``cleanup_fn()``
    when done (analogous to TemporaryDirectory.__exit__).
    """
    tmpdir = tempfile.mkdtemp(prefix="ovx_clone_")
    clone = Path(tmpdir) / base.name

    # Try copy-on-write first (fast on btrfs/apfs), then plain copy.
    # We do NOT use -l (hard links) because mutating the clone would mutate the base.
    result = subprocess.run(  # noqa: S603
        ["cp", "--reflink=auto", "-r", str(base), str(clone)],  # noqa: S607
        capture_output=True,
    )
    if result.returncode != 0:
        shutil.copytree(base, clone, symlinks=True)

    _patch_pyvenv_cfg(clone, base)

    def cleanup():
        shutil.rmtree(tmpdir, ignore_errors=True)

    return clone, cleanup


def _patch_pyvenv_cfg(clone: Path, base: Path) -> None:
    """Rewrite pyvenv.cfg in the clone so it no longer references the base path."""
    cfg = clone / "pyvenv.cfg"
    if not cfg.exists():
        return
    text = cfg.read_text()
    # Replace the prompt so it reflects the clone name, not the base name
    text = text.replace(f"prompt = {base.name}", f"prompt = {clone.name}")
    cfg.write_text(text)


def install_missing_python_deps(clone: Path, manifest: dict) -> list[str]:
    """Install any python external_dependencies missing from the clone venv.

    Returns the list of packages that were actually installed.
    """
    deps: list[str] = manifest.get("external_dependencies", {}).get("python", [])
    if not deps:
        return []

    installed = _freeze_venv(clone)
    missing = [dep for dep in deps if re.sub(r"[-_.]+", "-", dep).lower() not in installed]
    if not missing:
        return []

    subprocess.run(  # noqa: S603
        ["uv", "pip", "install", "--python", str(clone), *missing],  # noqa: S607
        check=True,
    )
    return missing
