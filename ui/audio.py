"""
ui/audio.py

Plays a short reference tone for a MIDI note (reinforces correct answers).
Honors the Mute / Volume preferences (core.prefs). The tone is synthesized
as an in-memory WAV (sine + harmonics with a quick decay envelope) and
played through the stdlib `winsound` module on a background thread, so the
GUI never blocks. Silent no-op off Windows.

(winsound can't combine SND_MEMORY with SND_ASYNC, hence the thread plus
a synchronous PlaySound call.)
"""

import io
import math
import struct
import threading
import wave

from core.prefs import Prefs

try:
    import winsound
    _WINSOUND_AVAILABLE = True
except ImportError:
    _WINSOUND_AVAILABLE = False

DEFAULT_DURATION_MS = 450
SAMPLE_RATE = 22050
_play_lock = threading.Lock()


def midi_to_frequency_hz(midi_note: int) -> float:
    """Equal temperament, A4 (midi 69) = 440 Hz."""
    return 440.0 * (2 ** ((midi_note - 69) / 12))


def synth_wav(midi_note: int, duration_ms: int = DEFAULT_DURATION_MS, volume: float = 0.7) -> bytes:
    """Returns a complete mono 16-bit WAV file as bytes. volume: 0.0-1.0."""
    volume = max(0.0, min(1.0, volume))
    freq = midi_to_frequency_hz(midi_note)
    n = int(SAMPLE_RATE * duration_ms / 1000)
    frames = bytearray()
    for i in range(n):
        t = i / SAMPLE_RATE
        # Plucked-ish: fundamental + two softer harmonics, exponential decay,
        # short attack to avoid a click.
        wave_val = (math.sin(2 * math.pi * freq * t)
                    + 0.35 * math.sin(2 * math.pi * 2 * freq * t)
                    + 0.15 * math.sin(2 * math.pi * 3 * freq * t)) / 1.5
        env = math.exp(-5.0 * t / (duration_ms / 1000)) * min(1.0, i / 100)
        frames += struct.pack("<h", int(32767 * 0.6 * volume * env * wave_val))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def is_muted() -> bool:
    prefs = Prefs.instance()
    return bool(prefs.get("sound_muted")) or int(prefs.get("sound_volume")) <= 0


def play_note_tone(midi_note: int, duration_ms: int = DEFAULT_DURATION_MS, force: bool = False) -> None:
    """Fire-and-forget. Skipped when muted (unless `force`, used by the
    Settings 'Test sound' button so volume can be previewed)."""
    if not _WINSOUND_AVAILABLE:
        return
    prefs = Prefs.instance()
    if not force and is_muted():
        return
    volume = int(prefs.get("sound_volume")) / 100.0
    if volume <= 0:
        return

    def _run() -> None:
        data = synth_wav(midi_note, duration_ms, volume)
        with _play_lock:
            winsound.PlaySound(data, winsound.SND_MEMORY)

    threading.Thread(target=_run, daemon=True).start()
