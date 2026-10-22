"""
core/notes.py

Canonical note representation for the fretboard trainer app.

Design principle: MIDI note number is the single source of truth for pitch
identity. Pitch class (0-11) and octave are always derived from it, never
stored independently. Enharmonic pairs (C#/Db, D#/Eb, etc.) are represented
as ONE pitch class with multiple valid display names -- there is no separate
"C#" object and "Db" object anywhere in this model. This makes it structurally
impossible to accidentally offer both spellings as separate multiple-choice
answers, and trivial to accept either spelling as correct input.
"""

from dataclasses import dataclass

# Pitch class (0-11) -> list of valid display names.
# Index 0 = C, matching standard MIDI convention (MIDI % 12 == 0 is a C).
PITCH_CLASS_NAMES: dict[int, list[str]] = {
    0: ["C"],
    1: ["C#", "Db"],
    2: ["D"],
    3: ["D#", "Eb"],
    4: ["E"],
    5: ["F"],
    6: ["F#", "Gb"],
    7: ["G"],
    8: ["G#", "Ab"],
    9: ["A"],
    10: ["A#", "Bb"],
    11: ["B"],
}

# Reverse lookup: any accepted display name (case-insensitive) -> pitch class.
_NAME_TO_PITCH_CLASS: dict[str, int] = {
    name.upper(): pc
    for pc, names in PITCH_CLASS_NAMES.items()
    for name in names
}


@dataclass(frozen=True)
class Note:
    """A specific pitch: one exact MIDI note number."""

    midi: int

    @property
    def pitch_class(self) -> int:
        """0-11, where 0 = C. Determines which note name(s) apply."""
        return self.midi % 12

    @property
    def octave(self) -> int:
        """Scientific pitch notation octave (MIDI 60 = C4 = middle C)."""
        return (self.midi // 12) - 1

    @property
    def names(self) -> list[str]:
        """All valid display spellings for this note's pitch class, e.g. ['C#', 'Db']."""
        return PITCH_CLASS_NAMES[self.pitch_class]

    @property
    def display_name(self) -> str:
        """Primary (sharp-preferred) spelling, for when only one name is needed."""
        return self.names[0]

    @property
    def display_name_with_octave(self) -> str:
        """e.g. 'C#4' -- used for Live Play Mode's specific-octave prompts (v4)."""
        return f"{self.display_name}{self.octave}"

    def matches_name(self, name: str) -> bool:
        """True if `name` (any accepted spelling, case-insensitive) names this note's pitch class."""
        return _NAME_TO_PITCH_CLASS.get(name.strip().upper()) == self.pitch_class

    def is_same_pitch_class(self, other: "Note") -> bool:
        """True if two notes are the same pitch class regardless of octave (e.g. C3 vs C5)."""
        return self.pitch_class == other.pitch_class

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Note):
            return NotImplemented
        return self.midi == other.midi

    def __repr__(self) -> str:
        return f"Note(midi={self.midi}, name={self.display_name_with_octave})"


def pitch_class_names(pitch_class: int) -> list[str]:
    """Look up display names for a raw pitch class (0-11) without needing a Note instance."""
    if pitch_class not in PITCH_CLASS_NAMES:
        raise ValueError(f"Invalid pitch class: {pitch_class}. Must be 0-11.")
    return PITCH_CLASS_NAMES[pitch_class]


def name_to_pitch_class(name: str) -> int:
    """Convert a display name (any accepted spelling) to its pitch class (0-11)."""
    pc = _NAME_TO_PITCH_CLASS.get(name.strip().upper())
    if pc is None:
        raise ValueError(f"Unrecognized note name: {name!r}")
    return pc
