from typer import BadParameter


class PresetNotFoundError(BadParameter):
    def __init__(self, preset: str) -> None:
        super().__init__(f"Preset '{preset}' not found.")
