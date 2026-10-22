"""
core/fretboard.py

Maps physical fretboard positions (string, fret) to notes, based on a tuning
definition. The valid note range is always CALCULATED from the tuning and
fret count -- never hardcoded -- so the app can never generate a note that
isn't physically playable (e.g. it will never ask for C1 or C2, since those
don't exist in the standard-tuned, 15-fret range).

String numbering follows standard guitar convention: String 1 = high E
(thinnest string), String 6 = low E (thickest string).
"""

from dataclasses import dataclass, field

from core.notes import Note

MAX_FRET = 15  # frets 0 (open string) through 15 are valid positions

# Standard tuning: string number -> open-string MIDI note.
# E2=40, A2=45, D3=50, G3=55, B3=59, E4=64
STANDARD_TUNING: dict[int, int] = {
    1: 64,  # E4 (high E, thinnest)
    2: 59,  # B3
    3: 55,  # G3
    4: 50,  # D3
    5: 45,  # A2
    6: 40,  # E2 (low E, thickest)
}


@dataclass
class Fretboard:
    """
    A fretboard for a given tuning. Owns all string/fret <-> note math and
    the enabled/disabled state of each string.

    Built as a class (not free functions) because "which strings are
    enabled" is stateful and every quiz mode + live play mode needs to
    consult it. Future tunings (v5+) are just a different `tuning` dict
    passed in here -- no other code changes.
    """

    tuning: dict[int, int] = field(default_factory=lambda: dict(STANDARD_TUNING))
    max_fret: int = MAX_FRET
    enabled_strings: set[int] = field(default_factory=lambda: {1, 2, 3, 4, 5, 6})
    # Active fret window for quizzing (inclusive). Defaults to the full neck.
    fret_min: int = 0
    fret_max: int | None = None

    def __post_init__(self) -> None:
        if self.fret_max is None:
            self.fret_max = self.max_fret
        if not self.tuning:
            raise ValueError("Tuning must define at least one string.")
        if self.max_fret < 0:
            raise ValueError("max_fret cannot be negative.")

    # --- string enable/disable ---------------------------------------

    def set_string_enabled(self, string: int, enabled: bool) -> None:
        """Zero enabled strings is a valid state here -- it just means no
        question can be generated yet (see QuizSession.next_question). The
        UI is responsible for not letting the quiz actually start with zero
        strings selected."""
        self._validate_string(string)
        if enabled:
            self.enabled_strings.add(string)
        else:
            self.enabled_strings.discard(string)

    # --- active fret range ---------------------------------------------

    def set_fret_range(self, lo: int, hi: int) -> None:
        """Clamp to the physical neck; if lo > hi they are swapped."""
        lo = max(0, min(self.max_fret, lo))
        hi = max(0, min(self.max_fret, hi))
        if lo > hi:
            lo, hi = hi, lo
        self.fret_min, self.fret_max = lo, hi

    def active_frets(self) -> range:
        return range(self.fret_min, self.fret_max + 1)

    def candidate_positions(self) -> list[tuple[int, int]]:
        """Every (string, fret) a quiz may ask about: enabled strings x active fret range."""
        return [(s, f) for s in self.get_enabled_strings() for f in self.active_frets()]

    def is_string_enabled(self, string: int) -> bool:
        self._validate_string(string)
        return string in self.enabled_strings

    def get_enabled_strings(self) -> list[int]:
        return sorted(self.enabled_strings)

    # --- position <-> note mapping -------------------------------------

    def note_at(self, string: int, fret: int) -> Note:
        """The Note produced by pressing `string` at `fret` (fret 0 = open string)."""
        self._validate_string(string)
        self._validate_fret(fret)
        return Note(midi=self.tuning[string] + fret)

    def all_positions_for_note(
        self, midi: int | None = None, pitch_class: int | None = None, enabled_only: bool = True
    ) -> list[tuple[int, int]]:
        """
        Find every (string, fret) position producing a given note.

        Pass `midi` for an EXACT pitch match (same note, same octave) --
        used by Live Play's Specific Octave mode, typically returns 0-2 positions.

        Pass `pitch_class` for ANY-OCTAVE match (same note name, any octave) --
        used by Live Play's Any Octave mode and Free Play, typically returns
        several positions across the neck.
        """
        if (midi is None) == (pitch_class is None):
            raise ValueError("Provide exactly one of `midi` or `pitch_class`.")

        strings = self.get_enabled_strings() if enabled_only else sorted(self.tuning.keys())
        positions = []
        for string in strings:
            for fret in range(0, self.max_fret + 1):
                note = self.note_at(string, fret)
                if midi is not None and note.midi == midi:
                    positions.append((string, fret))
                elif pitch_class is not None and note.pitch_class == pitch_class:
                    positions.append((string, fret))
        return positions

    # --- range calculation (never hardcoded) ----------------------------

    def lowest_note(self) -> Note:
        """The lowest playable note across all strings at fret 0 (regardless of enabled state --
        this is the instrument's physical range, not the currently-active quiz range)."""
        return Note(midi=min(self.tuning.values()))

    def highest_note(self) -> Note:
        """The highest playable note: highest open string + max_fret."""
        return Note(midi=max(self.tuning.values()) + self.max_fret)

    def valid_midi_range(self) -> range:
        """Full physically-playable MIDI range, inclusive, across ALL strings (enabled or not)."""
        return range(self.lowest_note().midi, self.highest_note().midi + 1)

    # --- validation ------------------------------------------------------

    def _validate_string(self, string: int) -> None:
        if string not in self.tuning:
            raise ValueError(f"Invalid string: {string}. Valid strings: {sorted(self.tuning.keys())}")

    def _validate_fret(self, fret: int) -> None:
        if not (0 <= fret <= self.max_fret):
            raise ValueError(f"Invalid fret: {fret}. Must be 0-{self.max_fret}.")
