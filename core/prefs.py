"""
core/prefs.py

Small JSON-backed preferences store (no UI dependency). Lives at
%APPDATA%\\FretboardTrainer\\settings.json (home directory elsewhere).
Reads are tolerant: a missing, corrupt, or wrong-typed value just falls
back to its default, so a bad settings file can never stop the app starting.
"""

import json
import os
from pathlib import Path

DEFAULTS: dict = {
    "enabled_strings": [1, 2, 3, 4, 5, 6],
    "fret_min": 0,
    "fret_max": 15,
    "quiz1_duration": 60,
    "quiz2_duration": 60,
    "accidental_mode": "RANDOM_MIX",
    "sound_muted": False,
    "sound_volume": 70,          # 0-100
    "precount_enabled": True,    # 3-2-1 before a quiz starts
    "window_geometry": "",       # hex of QMainWindow.saveGeometry()
    "skin": "Schoolhouse Pop",   # active full theme (see ui/skins)
}


def default_prefs_path() -> Path:
    appdata = os.getenv("APPDATA")
    base = Path(appdata) if appdata else Path.home()
    target = base / "FretboardTrainer"
    target.mkdir(parents=True, exist_ok=True)
    return target / "settings.json"


class Prefs:
    _instance: "Prefs | None" = None

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else default_prefs_path()
        self._data: dict = {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._data = loaded
        except (OSError, ValueError):
            pass

    @classmethod
    def instance(cls) -> "Prefs":
        if cls._instance is None:
            cls._instance = Prefs()
        return cls._instance

    def get(self, key: str):
        default = DEFAULTS[key]
        value = self._data.get(key, default)
        if type(value) is not type(default):
            return default
        return value

    def set(self, key: str, value) -> None:
        if key not in DEFAULTS:
            raise KeyError(key)
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self._save()

    def _save(self) -> None:
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass  # preferences are a convenience; never crash over them
