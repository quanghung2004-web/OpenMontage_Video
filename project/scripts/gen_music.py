#!/usr/bin/env python3
"""Stage 3: procedurally synthesize a documentary/epic score, offline.

No royalty-free music library is reachable from this sandbox (Pixabay,
Freesound, etc. are all blocked), so the score is generated from scratch
with numpy: layered sine/harmonic pads following mood-appropriate chord
progressions, a sub drone, soft percussion, and sparse melodic accents.
Output is one continuous stereo WAV per contiguous mood-region of the
video timeline, later concatenated to exactly match the picture length.
"""
from __future__ import annotations

import json
import struct
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "project"
MUSIC_DIR = PROJECT / "assets" / "audio" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

SR = 44100

NOTE_SEMITONE = {"C": -9, "C#": -8, "Db": -8, "D": -7, "D#": -6, "Eb": -6, "E": -5,
                 "F": -4, "F#": -3, "Gb": -3, "G": -2, "G#": -1, "Ab": -1, "A": 0,
                 "A#": 1, "Bb": 1, "B": 2}


def freq(note: str, octave: int) -> float:
    semis = NOTE_SEMITONE[note] + (octave - 4) * 12
    return 440.0 * (2 ** (semis / 12))


def t_axis(duration: float) -> np.ndarray:
    return np.linspace(0, duration, int(SR * duration), endpoint=False)


def sine(freq_hz: float, t: np.ndarray, phase: float = 0.0) -> np.ndarray:
    return np.sin(2 * np.pi * freq_hz * t + phase)


def harmonic_tone(freq_hz: float, t: np.ndarray, n_harmonics=5, rolloff=0.55) -> np.ndarray:
    """A warm, slightly bright tone built from a few harmonics (brass/pad-ish)."""
    out = np.zeros_like(t)
    for h in range(1, n_harmonics + 1):
        out += (rolloff ** (h - 1)) * np.sin(2 * np.pi * freq_hz * h * t)
    return out / np.sum([rolloff ** (h - 1) for h in range(1, n_harmonics + 1)])


def smooth(x: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return x
    kernel = np.ones(window) / window
    return np.convolve(x, kernel, mode="same")


def env_adsr(n: int, sr: int, attack: float, decay: float, sustain: float, release: float, hold: float) -> np.ndarray:
    a, d, r = int(attack * sr), int(decay * sr), int(release * sr)
    h = max(0, n - a - d - r)
    env = np.concatenate([
        np.linspace(0, 1, max(a, 1)),
        np.linspace(1, sustain, max(d, 1)),
        np.full(max(h, 1), sustain),
        np.linspace(sustain, 0, max(r, 1)),
    ])
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)))
    return env[:n]


def chord_pad(chord_freqs: list[float], duration: float, chord_seconds: float, octave_shift=0.0, brightness=4) -> np.ndarray:
    """Render a slowly-changing pad by looping through the chord list."""
    n_total = int(SR * duration)
    out = np.zeros(n_total)
    t_chord = t_axis(chord_seconds + 2.0)  # extra tail for crossfade
    n_chord = int(SR * chord_seconds)
    fade = int(SR * 1.5)
    pos = 0
    i = 0
    while pos < n_total:
        f_list = chord_freqs[i % len(chord_freqs)]
        layer = np.zeros(len(t_chord))
        for f in f_list:
            layer += harmonic_tone(f * (2 ** octave_shift), t_chord, n_harmonics=brightness)
        layer /= len(f_list)
        env = np.ones(len(t_chord))
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        seg = (layer * env)[:n_chord + fade]
        end = min(n_total, pos + len(seg))
        out[pos:end] += seg[: end - pos]
        pos += n_chord
        i += 1
    return out


def sub_drone(root_hz: float, duration: float, wobble_hz=0.07, wobble_depth=0.15) -> np.ndarray:
    t = t_axis(duration)
    wob = 1.0 + wobble_depth * np.sin(2 * np.pi * wobble_hz * t)
    return 0.6 * np.sin(2 * np.pi * root_hz * t * wob)


def pulse_track(duration: float, bpm: float, freq_hz: float, decay=0.35, beats_per_hit=1, accent_every=4) -> np.ndarray:
    n_total = int(SR * duration)
    out = np.zeros(n_total)
    beat_sec = 60.0 / bpm
    n_beats = int(duration / beat_sec)
    hit_len = min(decay * 2.2, beat_sec * 0.95)
    t_hit = t_axis(hit_len)
    for b in range(0, n_beats, beats_per_hit):
        accent = 1.0 if (b // beats_per_hit) % accent_every == 0 else 0.6
        click = np.sin(2 * np.pi * freq_hz * t_hit) * np.exp(-t_hit / decay)
        # slight pitch drop for a "thump" character
        click *= np.exp(-3 * t_hit)
        pos = int(b * beat_sec * SR)
        end = min(n_total, pos + len(click))
        out[pos:end] += accent * click[: end - pos]
    return out


def pluck_track(duration: float, note_times: list[float], freqs: list[float], decay=1.4, amp=0.5) -> np.ndarray:
    n_total = int(SR * duration)
    out = np.zeros(n_total)
    for nt, f in zip(note_times, freqs):
        nt = max(0.0, nt)
        if nt >= duration:
            continue
        length = min(decay * 3, duration - nt)
        t = t_axis(length)
        tone = harmonic_tone(f, t, n_harmonics=6, rolloff=0.4) * np.exp(-t / decay)
        pos = int(nt * SR)
        end = min(n_total, pos + len(tone))
        out[pos:end] += amp * tone[: end - pos]
    return out


def wind_texture(duration: float, amp=0.05, cutoff_window=400) -> np.ndarray:
    n = int(SR * duration)
    rng = np.random.default_rng(1234)
    noise = rng.standard_normal(n)
    shaped = smooth(noise, cutoff_window)
    shaped = shaped / (np.max(np.abs(shaped)) + 1e-9)
    # slow swell
    t = t_axis(duration)
    swell = 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t)
    return amp * shaped * swell


def normalize(x: np.ndarray, peak=0.72) -> np.ndarray:
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


def to_stereo_wav(mono: np.ndarray, path: Path, width_ms=6.0):
    """Cheap stereo widening: delay one channel by a few ms (Haas effect)."""
    delay = int(SR * width_ms / 1000)
    left = mono
    right = np.concatenate([np.zeros(delay), mono])[: len(mono)]
    stereo = np.stack([left, right], axis=1)
    stereo = np.clip(stereo, -1.0, 1.0)
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


# ------------------------------------------------------------ mood mixes --

def mood_tense(duration: float) -> np.ndarray:
    Dm = [freq("D", 3), freq("F", 3), freq("A", 3)]
    Bb = [freq("Bb", 2), freq("D", 3), freq("F", 3)]
    C = [freq("C", 3), freq("E", 3), freq("G", 3)]
    pad = chord_pad([Dm, Bb, C, Dm], duration, chord_seconds=7.5, brightness=3)
    drone = sub_drone(freq("D", 1), duration, wobble_hz=0.09, wobble_depth=0.22)
    pulse = pulse_track(duration, bpm=86, freq_hz=64, decay=0.5, accent_every=4)
    tremolo_t = t_axis(duration)
    tremolo = 0.10 * np.sin(2 * np.pi * freq("A", 4) * tremolo_t) * (0.5 + 0.5 * np.sin(2 * np.pi * 6.0 * tremolo_t))
    mix = 0.55 * pad + 0.35 * drone + 0.45 * pulse + tremolo
    return normalize(mix, 0.7)


def mood_mysterious(duration: float) -> np.ndarray:
    Dm = [freq("D", 3), freq("F", 3), freq("A", 3)]
    Gm = [freq("G", 2), freq("Bb", 2), freq("D", 3)]
    Asus = [freq("A", 2), freq("D", 3), freq("E", 3)]
    pad = chord_pad([Dm, Gm, Dm, Asus], duration, chord_seconds=10.0, brightness=2, octave_shift=-0.15)
    drone = sub_drone(freq("D", 1), duration, wobble_hz=0.05, wobble_depth=0.3)
    wind = wind_texture(duration, amp=0.08, cutoff_window=500)
    rng = np.random.default_rng(7)
    n_bells = max(3, int(duration / 14))
    bell_times = sorted(rng.uniform(4, duration - 4, n_bells))
    bell_freqs = [freq(n, 5) for n in rng.choice(["D", "F", "A", "C"], n_bells)]
    bells = pluck_track(duration, bell_times, bell_freqs, decay=2.2, amp=0.22)
    mix = 0.5 * pad + 0.3 * drone + wind + bells
    return normalize(mix, 0.62)


def mood_heroic(duration: float) -> np.ndarray:
    D = [freq("D", 3), freq("F#", 3), freq("A", 3)]
    A = [freq("A", 2), freq("C#", 3), freq("E", 3)]
    Bm = [freq("B", 2), freq("D", 3), freq("F#", 3)]
    G = [freq("G", 2), freq("B", 2), freq("D", 3)]
    pad = chord_pad([D, A, Bm, G], duration, chord_seconds=6.0, brightness=5)
    drone = sub_drone(freq("D", 2), duration, wobble_hz=0.1, wobble_depth=0.15)
    pulse = pulse_track(duration, bpm=104, freq_hz=72, decay=0.4, accent_every=4)
    rng = np.random.default_rng(3)
    arp_notes = ["D", "F#", "A", "D"]
    n_reps = int(duration / 2.2)
    arp_times = [i * 2.2 + rng.uniform(-0.05, 0.05) for i in range(n_reps)]
    arp_freqs = [freq(arp_notes[i % len(arp_notes)], 5) for i in range(n_reps)]
    arp = pluck_track(duration, arp_times, arp_freqs, decay=0.9, amp=0.16)
    mix = 0.55 * pad + 0.3 * drone + 0.5 * pulse + arp
    return normalize(mix, 0.75)


def mood_uplifting(duration: float) -> np.ndarray:
    D = [freq("D", 3), freq("F#", 3), freq("A", 3)]
    G = [freq("G", 2), freq("B", 2), freq("D", 3)]
    A = [freq("A", 2), freq("C#", 3), freq("E", 3)]
    pad = chord_pad([D, G, A, D], duration, chord_seconds=8.0, brightness=4, octave_shift=0.1)
    drone = sub_drone(freq("D", 2), duration, wobble_hz=0.06, wobble_depth=0.18)
    rng = np.random.default_rng(9)
    bell_notes = ["D", "F#", "A", "D", "G", "F#"]
    n_reps = int(duration / 1.8)
    bell_times = [i * 1.8 + rng.uniform(-0.05, 0.05) for i in range(n_reps)]
    bell_freqs = [freq(bell_notes[i % len(bell_notes)], 5) for i in range(n_reps)]
    bells = pluck_track(duration, bell_times, bell_freqs, decay=1.6, amp=0.20)
    shimmer = wind_texture(duration, amp=0.035, cutoff_window=180)
    mix = 0.5 * pad + 0.28 * drone + bells + shimmer
    return normalize(mix, 0.68)


MOOD_FN = {
    "tense": mood_tense,
    "mysterious": mood_mysterious,
    "heroic": mood_heroic,
    "uplifting": mood_uplifting,
}


def main():
    timeline_data = json.loads((PROJECT / "timeline.json").read_text())
    timeline = timeline_data["timeline"]

    # Group into contiguous mood regions (moods never interleave in this script).
    regions = []
    cur_mood = None
    cur_start = None
    cur_end = None
    for seg in timeline:
        mood = seg.get("mood", "tense")
        if mood != cur_mood:
            if cur_mood is not None:
                regions.append((cur_mood, cur_start, cur_end))
            cur_mood, cur_start = mood, seg["start"]
        cur_end = seg["start"] + seg["duration"]
    regions.append((cur_mood, cur_start, cur_end))

    manifest = []
    for idx, (mood, start, end) in enumerate(regions):
        duration = round(end - start, 3)
        fn = MOOD_FN[mood]
        print(f"Synthesizing region {idx}: mood={mood} duration={duration:.1f}s")
        audio = fn(duration + 0.5)  # small tail safety margin
        path = MUSIC_DIR / f"region_{idx:02d}_{mood}.wav"
        to_stereo_wav(audio, path)
        manifest.append({"index": idx, "mood": mood, "start": start, "end": end,
                          "duration": duration, "path": str(path.relative_to(ROOT))})

    (PROJECT / "music_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Generated {len(manifest)} music regions -> project/music_manifest.json")


if __name__ == "__main__":
    main()
