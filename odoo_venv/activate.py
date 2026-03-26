"""Activate a virtual environment by spawning a new interactive shell.

Uses os.execvpe() to replace the current process with a new shell that has
the venv activated — the "pipenv fancy mode" pattern. Supports bash, zsh.
"""

from __future__ import annotations

import os
import shlex
import tempfile
from pathlib import Path

import typer


def detect_shell() -> tuple[str, str]:
    """Detect the user's shell from $SHELL.

    Returns:
        (shell_name, shell_path) — e.g. ("bash", "/bin/bash").
        Falls back to ("sh", "/bin/sh") when $SHELL is unset.
    """
    shell_path = os.environ.get("SHELL", "/bin/sh")
    shell_name = Path(shell_path).name
    return shell_name, shell_path


def create_rcfile_bash(venv_path: Path) -> str:
    """Create a temp rcfile that sources the user's bashrc + venv activate.

    The rcfile deletes itself after being sourced so no temp files linger.

    Args:
        venv_path: Absolute path to the virtual environment directory.

    Returns:
        Path to the temporary rcfile.
    """
    bashrc = Path.home() / ".bashrc"
    activate = venv_path / "bin" / "activate"

    fd, rcfile = tempfile.mkstemp(prefix="odoo-venv-", suffix=".sh")
    with os.fdopen(fd, "w") as f:
        if bashrc.is_file():
            f.write(f"source {shlex.quote(str(bashrc))}\n")
        f.write(f"source {shlex.quote(str(activate))}\n")
        # Self-cleanup: remove the temp file after it's been sourced
        f.write(f"rm -f {shlex.quote(rcfile)}\n")
    return rcfile


def create_rcfile_zsh(venv_path: Path) -> str:
    """Create a temp ZDOTDIR with .zshrc that sources user's zshrc + activate.

    Zsh uses ZDOTDIR to locate .zshrc, so we create a temp directory containing
    a .zshrc that chains the user's original config and the venv activation.

    Args:
        venv_path: Absolute path to the virtual environment directory.

    Returns:
        Path to the temporary ZDOTDIR directory.
    """
    zdotdir = tempfile.mkdtemp(prefix="odoo-venv-")
    zshrc = Path(zdotdir) / ".zshrc"
    user_zshrc = Path(os.environ.get("ZDOTDIR", str(Path.home()))) / ".zshrc"
    activate = venv_path / "bin" / "activate"

    with open(zshrc, "w") as f:
        if user_zshrc.is_file():
            f.write(f"source {shlex.quote(str(user_zshrc))}\n")
        f.write(f"source {shlex.quote(str(activate))}\n")
        # Restore original ZDOTDIR before cleanup so nested zsh works
        original_zdotdir = os.environ.get("ZDOTDIR")
        if original_zdotdir:
            f.write(f"export ZDOTDIR={shlex.quote(original_zdotdir)}\n")
        else:
            f.write("unset ZDOTDIR\n")
        # Self-cleanup: remove the temp ZDOTDIR after sourcing
        f.write(f"rm -rf {shlex.quote(zdotdir)}\n")
    return zdotdir


def _clean_env() -> dict[str, str]:
    """Return a copy of os.environ with any active venv deactivated.

    Removes VIRTUAL_ENV and strips its bin/ directory from PATH so the
    new shell starts clean — prevents PATH accumulation on nested activates.
    """
    env = os.environ.copy()
    old_venv = env.pop("VIRTUAL_ENV", None)
    if old_venv:
        old_bin = str(Path(old_venv) / "bin")
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if p != old_bin)
    return env


def activate_venv(venv_dir: Path) -> None:
    """Spawn a new interactive shell with the venv activated.

    Detects the user's shell, creates an appropriate rcfile, then replaces
    the current process via os.execvpe(). This function never returns on success.

    Args:
        venv_dir: Absolute path to the virtual environment directory.
    """
    shell_name, shell_path = detect_shell()
    env = _clean_env()

    try:
        if shell_name == "bash":
            rcfile = create_rcfile_bash(venv_dir)
            os.execvpe(shell_path, [shell_path, "--rcfile", rcfile, "-i"], env)  # noqa: S606
        elif shell_name == "zsh":
            zdotdir = create_rcfile_zsh(venv_dir)
            env["ZDOTDIR"] = zdotdir
            os.execvpe(shell_path, [shell_path, "-i"], env)  # noqa: S606
        else:
            activate = venv_dir / "bin" / "activate"
            typer.secho(
                f"Unsupported shell '{shell_name}'. Activate manually:\n  source {activate}", fg=typer.colors.YELLOW
            )
            raise typer.Exit(1)
    except OSError as exc:
        typer.secho(f"error: failed to start shell '{shell_path}': {exc}", fg=typer.colors.RED)
        raise typer.Exit(1) from exc
