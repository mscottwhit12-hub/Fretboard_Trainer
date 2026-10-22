"""
core/settings.py

App-wide gameplay rules that affect quiz question generation. Kept in
core/ (no UI framework dependency) so both core/quiz1.py, core/quiz2.py,
and the Settings > Game Rules UI panel all read/write the same single
source of truth.
"""

import random
from enum import Enum

from core.prefs import Prefs


class AccidentalMode(Enum):
    """How sharp vs. flat spellings are chosen for a note that has both
    (e.g. C#/Db). Naturals (C, D, E, F, G, A, B) are unaffected -- they
    only have one spelling."""

    ALL_SHARPS = "all_sharps"
    ALL_FLATS = "all_flats"
    RANDOM_MIX = "random_mix"       # default -- 50/50 per note
    FAVOR_SHARPS = "favor_sharps"   # ~70/30 toward sharps
    FAVOR_FLATS = "favor_flats"     # ~70/30 toward flats


ACCIDENTAL_MODE_LABELS: dict[AccidentalMode, str] = {
    AccidentalMode.ALL_SHARPS: "All sharps",
    AccidentalMode.ALL_FLATS: "All flats",
    AccidentalMode.RANDOM_MIX: "Random mix",
    AccidentalMode.FAVOR_SHARPS: "Slightly favor sharps",
    AccidentalMode.FAVOR_FLATS: "Slightly favor flats",
}

DEFAULT_ACCIDENTAL_MODE = AccidentalMode.RANDOM_MIX
_FAVOR_WEIGHT = 0.7  # probability of the favored spelling under FAVOR_* modes


class GameRules:
    """Singleton holding the current gameplay settings. The accidental
    mode is persisted via core.prefs."""

    _instance: "GameRules | None" = None

    def __init__(self):
        try:
            self._mode = AccidentalMode[Prefs.instance().get("accidental_mode")]
        except KeyError:
            self._mode = DEFAULT_ACCIDENTAL_MODE

    @property
    def accidental_mode(self) -> AccidentalMode:
        return self._mode

    @accidental_mode.setter
    def accidental_mode(self, mode: AccidentalMode) -> None:
        self._mode = mode
        Prefs.instance().set("accidental_mode", mode.name)

    @classmethod
    def instance(cls) -> "GameRules":
        if cls._instance is None:
            cls._instance = GameRules()
        return cls._instance

    def choose_spelling(self, names: list[str], rng: random.Random) -> str:
        """Picks a display spelling for a pitch class's `names` (e.g.
        ["C#", "Db"]) according to the current accidental mode. Naturals
        (a single-element `names` list) always just return their one name."""
        if len(names) == 1:
            return names[0]

        sharp_name = next((n for n in names if "#" in n), names[0])
        flat_name = next((n for n in names if n != sharp_name), names[-1])

        mode = self.accidental_mode
        if mode is AccidentalMode.ALL_SHARPS:
            return sharp_name
        if mode is AccidentalMode.ALL_FLATS:
            return flat_name
        if mode is AccidentalMode.FAVOR_SHARPS:
            return sharp_name if rng.random() < _FAVOR_WEIGHT else flat_name
        if mode is AccidentalMode.FAVOR_FLATS:
            return flat_name if rng.random() < _FAVOR_WEIGHT else sharp_name
        # RANDOM_MIX (default) and any unrecognized fallback
        return rng.choice(names)
