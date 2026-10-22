"""
Quick sanity check for core/notes.py and core/fretboard.py.
Run directly: python test_core_sanity.py
No dependencies -- stdlib only.
"""

import random
import tempfile
from pathlib import Path

from core.fretboard import Fretboard
from core.notes import Note, name_to_pitch_class, pitch_class_names
from core.quiz1 import QuizSession
from data.db import HistoryDB

fb = Fretboard()

checks = []

# Open low E string (string 6, fret 0) must be E2, midi 40 -- the app's stated floor.
n = fb.note_at(6, 0)
checks.append(("Open string 6 = E2", n.midi == 40 and n.display_name == "E" and n.octave == 2))

# Open high E string (string 1, fret 0) must be E4, midi 64.
n = fb.note_at(1, 0)
checks.append(("Open string 1 = E4", n.midi == 64 and n.octave == 4))

# Highest note: string 1, fret 15 -> should be G5 (midi 79).
n = fb.note_at(1, 15)
checks.append(("String 1 fret 15 = G5 (midi 79)", n.midi == 79 and n.display_name == "G" and n.octave == 5))

# Range must be computed E2 -> G5, matching the spec's stated real guitar range.
lo, hi = fb.lowest_note(), fb.highest_note()
checks.append(("Computed range floor = E2", lo.midi == 40))
checks.append(("Computed range ceiling = G5", hi.midi == 79))

# Enharmonic pair: string 1 fret 4 = midi 68 -> pitch class 8 -> G#/Ab
n = fb.note_at(1, 4)
checks.append(("String 1 fret 4 names include G# and Ab", set(n.names) == {"G#", "Ab"}))
checks.append(("matches_name accepts G#", n.matches_name("G#")))
checks.append(("matches_name accepts Ab (case-insensitive, lowercase)", n.matches_name("ab")))
checks.append(("matches_name rejects wrong note", not n.matches_name("A")))

# name_to_pitch_class: both spellings of the same note must resolve to the same pitch class.
checks.append(("C# and Db resolve to same pitch class", name_to_pitch_class("C#") == name_to_pitch_class("Db")))

# String toggling
fb2 = Fretboard()
fb2.set_string_enabled(1, False)
checks.append(("Disabling string 1 removes it from enabled list", 1 not in fb2.get_enabled_strings()))
checks.append(("Other strings remain enabled", fb2.get_enabled_strings() == [2, 3, 4, 5, 6]))

for s in [2, 3, 4, 5, 6]:
    fb2.set_string_enabled(s, False)
checks.append(("Disabling all 6 strings is now allowed (no exception)", fb2.get_enabled_strings() == []))

# all_positions_for_note: G# (pitch class 8) any-octave, should find multiple spots.
positions = fb.all_positions_for_note(pitch_class=8)
checks.append((f"G# any-octave found {len(positions)} positions (expect > 1)", len(positions) > 1))

# all_positions_for_note: exact midi 68 (G#4), should typically find only 1-2 spots.
exact_positions = fb.all_positions_for_note(midi=68)
checks.append((f"G#4 exact-pitch found {len(exact_positions)} positions: {exact_positions}", len(exact_positions) >= 1))

# Never generates an out-of-range note like C1 or C2.
all_midis_in_use = {fb.note_at(s, f).midi for s in fb.get_enabled_strings() for f in range(0, fb.max_fret + 1)}
c1_midi = 24  # C1
c2_midi = 36  # C2
checks.append(("C1 never appears in any valid position", c1_midi not in all_midis_in_use))
checks.append(("C2 never appears in any valid position", c2_midi not in all_midis_in_use))

# --- Quiz Mode 1 (core/quiz1.py) checks ---

fb3 = Fretboard()
session = QuizSession(fb3, shuffle_enabled=True, shuffle_interval=10, rng=random.Random(42))

q = session.next_question()
checks.append(("Question string is enabled", q.string in fb3.get_enabled_strings()))
checks.append(("Question fret is in valid range", 0 <= q.fret <= fb3.max_fret))
checks.append(("Question has 4 choices by default", len(q.choices) == 4))

correct_pcs = [pc for pc, _name in q.choices if pc == q.correct_note.pitch_class]
checks.append(("Exactly one choice matches the correct pitch class", len(correct_pcs) == 1))

choice_pcs = [pc for pc, _name in q.choices]
checks.append(("No duplicate pitch classes among choices", len(choice_pcs) == len(set(choice_pcs))))

# Submitting the correct answer (using the OTHER enharmonic spelling than the
# one shown) must still be graded correct -- proves both spellings are accepted.
correct_choice_name = next(name for pc, name in q.choices if pc == q.correct_note.pitch_class)
alt_spelling = [n for n in q.correct_note.names if n != correct_choice_name]
answer_to_submit = alt_spelling[0] if alt_spelling else correct_choice_name
result = session.submit_answer(answer_to_submit)
checks.append(("Alternate enharmonic spelling is graded correct", result.correct is True))
checks.append(("AnswerResult response_time_ms is non-negative", result.response_time_ms >= 0))

# Wrong answer must be graded incorrect.
q2 = session.next_question()
wrong_pc = next(pc for pc in range(12) if pc != q2.correct_note.pitch_class)
wrong_name = pitch_class_names(wrong_pc)[0]
result2 = session.submit_answer(wrong_name)
checks.append(("Genuinely wrong answer is graded incorrect", result2.correct is False))

# Calling submit_answer with no active question must raise.
try:
    session.submit_answer("C")
    checks.append(("submit_answer with no active question should have raised", False))
except ValueError:
    checks.append(("submit_answer with no active question raises ValueError", True))

# next_question with zero enabled strings must raise.
fb_empty = Fretboard()
for s in [1, 2, 3, 4, 5]:
    fb_empty.set_string_enabled(s, False)
fb_empty.enabled_strings.discard(6)  # bypass the "keep at least one" guard directly for this test
empty_session = QuizSession(fb_empty)
try:
    empty_session.next_question()
    checks.append(("next_question with zero enabled strings should have raised", False))
except ValueError:
    checks.append(("next_question with zero enabled strings raises ValueError", True))

# --- HistoryDB (data/db.py) checks ---

with tempfile.TemporaryDirectory() as tmp_dir:
    test_db_path = Path(tmp_dir) / "test_history.db"

    with HistoryDB(test_db_path) as db:
        checks.append(("DB file created on disk", test_db_path.exists()))
        checks.append(("New DB starts with 0 attempts", db.count_attempts() == 0))

        # Log a fresh quiz session's worth of results through the real QuizSession,
        # to prove AnswerResult -> log_attempt actually round-trips correctly.
        fb4 = Fretboard()
        db_session = QuizSession(fb4, rng=random.Random(7))
        logged_correct_flags = []
        logged_midi_notes = []
        for _ in range(5):
            q = db_session.next_question()
            correct_name = next(name for pc, name in q.choices if pc == q.correct_note.pitch_class)
            res = db_session.submit_answer(correct_name)  # always answer correctly here
            db.log_attempt(res, quiz_mode="fret_to_note")
            logged_correct_flags.append(res.correct)
            logged_midi_notes.append(res.midi_note)

        checks.append(("5 attempts logged", db.count_attempts() == 5))
        checks.append(("All 5 logged attempts were correct", all(logged_correct_flags)))

        records = db.get_all_attempts(quiz_mode="fret_to_note")
        checks.append(("get_all_attempts returns 5 records", len(records) == 5))
        checks.append(("Filtering by a mode with no data returns 0", len(db.get_all_attempts(quiz_mode="note_to_fret")) == 0))
        checks.append(("Retrieved record has correct=True stored/read back as bool", records[0].correct is True))
        checks.append((
            "Retrieved midi_note values match exactly what was submitted, in order",
            [r.midi_note for r in records] == logged_midi_notes,
        ))
        checks.append(("Retrieved records are in ascending timestamp order", records == sorted(records, key=lambda r: r.timestamp)))

    # Reopen the same file fresh -- proves persistence survives closing the connection.
    with HistoryDB(test_db_path) as db_reopened:
        checks.append(("Data persists after reconnecting to the same DB file", db_reopened.count_attempts() == 5))

# --- Report results ---
print(f"{'PASS' if all(ok for _, ok in checks) else 'FAIL'} -- {sum(ok for _, ok in checks)}/{len(checks)} checks passed\n")
for label, ok in checks:
    print(f"  [{'x' if ok else ' '}] {label}")


# --- QoL batch: fret range + prefs -------------------------------------------
from core.prefs import Prefs
_fr = Fretboard(); _fr.set_fret_range(9, 4)
_ok = [("Fret range swaps reversed bounds", (_fr.fret_min, _fr.fret_max) == (4, 9))]
_ok.append(("candidate_positions limited to range x strings", len(_fr.candidate_positions()) == 6 * 6))
_fr.set_fret_range(7, 7)
for _s in (2, 3, 4, 5, 6): _fr.set_string_enabled(_s, False)
_q = QuizSession(_fr, rng=random.Random(1))
_ok.append(("Single-position pool does not hang", _q.next_question() and _q.next_question() is not None))
with tempfile.TemporaryDirectory() as _d:
    _p = Prefs(Path(_d) / "s.json"); _p.set("sound_volume", 33)
    _ok.append(("Prefs round-trip", Prefs(Path(_d) / "s.json").get("sound_volume") == 33))
    (Path(_d) / "bad.json").write_text("{oops")
    _ok.append(("Corrupt prefs fall back to defaults", Prefs(Path(_d) / "bad.json").get("sound_volume") == 70))
for _n, _c in _ok:
    print(("  [x] " if _c else "  [ ] FAIL ") + _n)
