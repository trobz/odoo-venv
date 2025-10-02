import ast
import subprocess
import sys
from pathlib import Path
import os
import re
import tempfile
import typer
from typing import Optional, List

PKG_NAME_PATTERN = re.compile(r"(?P<lib_name>[a-z0-9A-Z\-\_\.]+)((>|<|=)=)?(.*)")


def _run_command(
    command: List[str],
    venv_dir: Optional[Path] = None,
    cwd: Optional[Path] = None,
):
    env = os.environ.copy()
    if venv_dir:
        env["PATH"] = str(venv_dir / "bin") + os.pathsep + env["PATH"]
        env["VIRTUAL_ENV"] = str(venv_dir)

    result = subprocess.run(
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


def _get_python_version_from_odoo_src(odoo_dir: Path) -> Optional[str]:
    init_py = odoo_dir / "odoo" / "__init__.py"
    if not init_py.is_file():
        return None

    content = init_py.read_text()
    match = re.search(r"MIN_PY_VERSION\s*=\s*\((\d+),\s*(\d+)\)", content)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return None


def _find_manifest_files(addons_paths: List[str]) -> List[Path]:
    manifest_files = []
    for path in addons_paths:
        for root, _, files in os.walk(path):
            if "__manifest__.py" in files:
                manifest_files.append(Path(root) / "__manifest__.py")
    return manifest_files


def create_odoo_venv(
    odoo_version: str,
    odoo_dir: str,
    venv_dir: str,
    python_version: Optional[str],
    install_odoo: bool = True,
    install_odoo_requirements: bool = True,
    ignore_from_odoo_requirements: Optional[str] = None,
    addons_paths: Optional[List[str]] = None,
    install_addons_dirs_requirements: bool = False,
    ignore_from_addons_dirs_requirements: Optional[str] = None,
    install_addons_manifests_requirements: bool = False,
    ignore_from_addons_manifests_requirements: Optional[str] = None,
    extra_requirements_file: Optional[str] = None,
    extra_requirements: Optional[List[str]] = None,
):
    odoo_dir = Path(odoo_dir).expanduser().resolve()
    venv_dir = Path(venv_dir).expanduser().resolve()

    # 1. Determine Python version
    if not python_version:
        python_version = _get_python_version_from_odoo_src(odoo_dir)

    # 2. Create virtual environment
    _run_command(["uv", "venv", str(venv_dir), "--python", python_version])

    # 3. Install Odoo in editable mode
    if install_odoo:
        _run_command(
            ["uv", "pip", "install", "-e", f"file://{odoo_dir}#egg=odoo"],
            venv_dir=venv_dir,
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

    to_ignore = set()
    if ignore_from_odoo_requirements:
        to_ignore.update(
            {
                pkg.strip().lower()
                for pkg in ignore_from_odoo_requirements.split(",")
                if pkg.strip()
            }
        )
    if ignore_from_addons_dirs_requirements:
        to_ignore.update(
            {
                pkg.strip().lower()
                for pkg in ignore_from_addons_dirs_requirements.split(",")
                if pkg.strip()
            }
        )
    if ignore_from_addons_manifests_requirements:
        to_ignore.update(
            {
                pkg.strip().lower()
                for pkg in ignore_from_addons_manifests_requirements.split(",")
                if pkg.strip()
            }
        )

    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt", encoding="utf-8"
    ) as tmp:
        tmp_path = tmp.name
        req_count = 0

        if all_req_files:
            for req_file in all_req_files:
                with open(req_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        match = PKG_NAME_PATTERN.match(line)
                        if match:
                            pkg_name = match.group("lib_name").lower().strip()
                            if pkg_name in to_ignore:
                                continue
                        tmp.write(line + "\n")
                        req_count += 1

        if extra_requirements:
            for req in extra_requirements:
                req = req.strip()
                if not req:
                    continue
                tmp.write(req + "\n")
                req_count += 1

        if extra_requirements_file:
            extra_req_file = Path(extra_requirements_file).expanduser().resolve()
            if extra_req_file.exists():
                with open(extra_req_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        tmp.write(line + "\n")
                        req_count += 1

        if install_addons_manifests_requirements and addons_paths:
            manifest_files = _find_manifest_files(addons_paths)
            for manifest_file in manifest_files:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    manifest = ast.literal_eval(content)
                    if "external_dependencies" in manifest and isinstance(
                        manifest["external_dependencies"].get("python"), list
                    ):
                        for dep in manifest["external_dependencies"]["python"]:
                            match = PKG_NAME_PATTERN.match(dep)
                            if match:
                                pkg_name = match.group("lib_name").lower().strip()
                                if pkg_name in to_ignore:
                                    continue
                            tmp.write(dep + "\n")
                            req_count += 1

    if req_count > 0:
        install_args = [
            "uv",
            "pip",
            "install",
            "--no-deps",
            "-r",
            tmp_path,
        ]
        _run_command(install_args, venv_dir=venv_dir)

    os.remove(tmp_path)

    typer.secho(f"Virtual env: {venv_dir}", fg=typer.colors.GREEN)
    typer.secho(
        f"Activate it with: source {venv_dir}/bin/activate",
        fg=typer.colors.YELLOW,
    )
