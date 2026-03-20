from pathlib import Path


def update_presets_file():
    user_preset_path = Path("~/.local/share/odoo-venv/").expanduser() / "presets.toml"
    backup_path = user_preset_path.with_suffix(".toml.bak")
    user_preset_path.rename(backup_path)
    user_preset_path.write_text((Path(__file__).parent.parent / "assets" / "presets.toml").read_text())


if __name__ == "__main__":
    update_presets_file()
