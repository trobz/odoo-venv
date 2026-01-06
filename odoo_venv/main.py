import ast
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import typer
from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import parse as parse_version

PKG_NAME_PATTERN = re.compile(r"(?P<lib_name>[a-z0-9A-Z\-\_\.]+)((>|<|=)=)?(.*)")


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


def _run_command(
    command: list[str],
    venv_dir: Path | None = None,
    cwd: Path | None = None,
    verbose: bool = False,
    dry_run: bool = False,
):
    if verbose:
        typer.secho(f"  → Running: {' '.join(command)}", fg=typer.colors.BLUE)

    if dry_run:
        return

    env = os.environ.copy()
    if venv_dir:
        env["PATH"] = str(venv_dir / "bin") + os.pathsep + env["PATH"]
        env["VIRTUAL_ENV"] = str(venv_dir)

    # safe to ignore S603 as shell=False
    result = subprocess.run(  # noqa: S603
        command,
        env=env,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        typer.echo(result.stderr, file=sys.stderr)
        sys.exit(1)
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
        if req.name.lower() in ignored_req_map:
            for ignored_req in ignored_req_map[req.name.lower()]:
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
    verbose: bool = False,
    dry_run: bool = False,
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
    venv_command = ["uv", "venv", str(venv_dir)]
    if python_version:
        venv_command.extend(["--python", python_version])
    _run_command(
        venv_command,
        verbose=verbose,
        dry_run=dry_run,
    )
    typer.secho(
        f"  ✔ Virtual environment created at {typer.style(str(venv_dir), fg=typer.colors.YELLOW)}",
    )

    # 3. Install Odoo in editable mode
    if install_odoo:
        typer.secho("\nInstalling Odoo in editable mode...")
        _run_command(
            ["uv", "pip", "install", "-e", f"file://{odoo_dir}#egg=odoo"],
            venv_dir=venv_dir,
            verbose=verbose,
            dry_run=dry_run,
        )
        typer.secho(
            "  ✔  Installed Odoo in editable mode",
        )

    # 4. Install requirements
    all_req_files = []
    if install_odoo_requirements:
        odoo_reqs_file = odoo_dir / "requirements.txt"
        if odoo_reqs_file.exists():
            all_req_files.append(odoo_reqs_file)

    if install_addons_dirs_requirements and addons_paths:
        for path in addons_paths:
            addons_req_file = Path(path) / "requirements.txt"
            if addons_req_file.exists():
                all_req_files.append(addons_req_file)

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

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as tmp:
        tmp_path = tmp.name
        req_count = 0

        if all_req_files:
            for req_file in all_req_files:
                with open(req_file, encoding="utf-8") as f:
                    for line in f:
                        if _process_requirement_line(line, ignored_req_map, tmp, target_env_for_markers):
                            req_count += 1

        if extra_requirements:
            for req_line in extra_requirements:
                if _process_requirement_line(req_line, ignored_req_map, tmp, target_env_for_markers):
                    req_count += 1

        if extra_requirements_file:
            extra_req_file = Path(extra_requirements_file).expanduser().resolve()
            if extra_req_file.exists():
                with open(extra_req_file, encoding="utf-8") as f:
                    for line in f:
                        if _process_requirement_line(line, ignored_req_map, tmp, target_env_for_markers):
                            req_count += 1

        if install_addons_manifests_requirements and addons_paths:
            manifest_files = _find_manifest_files(addons_paths)
            for manifest_file in manifest_files:
                with open(manifest_file, encoding="utf-8") as f:
                    content = f.read()
                    manifest = ast.literal_eval(content)
                    if "external_dependencies" in manifest and isinstance(
                        manifest["external_dependencies"].get("python"), list
                    ):
                        for dep in manifest["external_dependencies"]["python"]:
                            if _process_requirement_line(
                                dep,
                                ignored_req_map,
                                tmp,
                                target_env_for_markers,
                            ):
                                req_count += 1

    if req_count > 0:
        install_args = [
            "uv",
            "pip",
            "install",
            "-r",
            tmp_path,
        ]
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

        _run_command(install_args, venv_dir=venv_dir, verbose=False, dry_run=dry_run)
        typer.secho(f"  ✔  {typer.style(req_count, fg=typer.colors.YELLOW)} Packages installed successfully")

    os.remove(tmp_path)

    typer.secho("\n✅ Environment setup complete!", fg=typer.colors.GREEN)
    typer.secho(
        f"Activate it with: source {typer.style(str(venv_dir / 'bin' / 'activate'), fg=typer.colors.YELLOW)}",
    )
