"""Procedural soft lo-fi bed (numpy only): Rhodes-like chords, bass, brushed drums."""
import json, sys
from pathlib import Path
import numpy as np, soundfile as sf
ROOT = Path(__file__).resolve().parents[1]
SR, BPM = 44100, 78
BEAT = 60 / BPM
rng = np.random.default_rng(3)

def note(f, dur, amp=0.2, decay=2.5):
    t = np.arange(int(dur * SR)) / SR
    env = np.exp(-decay * t) * np.minimum(1, t / 0.01)
    w = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) * np.exp(-6 * t) + 0.12 * np.sin(6 * np.pi * f * t) * np.exp(-9 * t)
    trem = 1 + 0.08 * np.sin(2 * np.pi * 4.5 * t)
    return amp * w * env * trem

def midi(m): return 440 * 2 ** ((m - 69) / 12)

PROGS = [  # (root midi, chord tones) 4 bars each
    [(48, [60, 64, 67, 71]), (45, [57, 60, 64, 67]), (41, [57, 60, 64, 65]), (43, [59, 62, 65, 67])],
    [(41, [57, 60, 64, 65]), (43, [59, 62, 65, 67]), (40, [55, 59, 62, 64]), (45, [57, 60, 64, 67])],
]

def bar(root, chord, var):
    n = int(4 * BEAT * SR); out = np.zeros(n + SR * 3)
    for i, m in enumerate(chord):
        s = int((0.03 * i) * SR); out[s:s + int(3.2 * BEAT * SR)] += note(midi(m), 3.2 * BEAT, 0.045, 1.2)
    if var % 2:
        s = int(2.5 * BEAT * SR); m = chord[(var // 2) % 4] + 12
        out[s:s + int(BEAT * SR)] += note(midi(m), BEAT, 0.03, 3)
    for b, l in ((0, 1.5), (2, 1.5)):
        s = int(b * BEAT * SR); out[s:s + int(l * BEAT * SR)] += note(midi(root - 12), l * BEAT, 0.11, 2.0)
    for b in range(4):  # kick on 1,3; snare-ish brush on 2,4; hats on 8ths
        s = int(b * BEAT * SR)
        if b % 2 == 0:
            t = np.arange(int(0.25 * SR)) / SR
            out[s:s + len(t)] += 0.16 * np.sin(2 * np.pi * (50 + 60 * np.exp(-25 * t)) * t) * np.exp(-12 * t)
        else:
            t = np.arange(int(0.2 * SR)) / SR
            out[s:s + len(t)] += 0.035 * rng.standard_normal(len(t)) * np.exp(-18 * t)
        for h in (0, 0.5):
            s2 = int((b + h + 0.02 * rng.random()) * BEAT * SR); t = np.arange(int(0.05 * SR)) / SR
            hn = rng.standard_normal(len(t)); hn = np.diff(hn, prepend=0)
            out[s2:s2 + len(t)] += 0.012 * hn * np.exp(-60 * t)
    return out, n

def main():
    total = json.load(open(ROOT / "timeline.json"))["total"] + 2
    L = int(total * SR); out = np.zeros(L + SR * 6); pos = 0; k = 0
    while pos < L:
        prog = PROGS[(k // 4) % 2]; root, chord = prog[k % 4]
        b, n = bar(root, chord, k); out[pos:pos + len(b)] += b[:len(out) - pos]; pos += n; k += 1
    out = out[:L]
    # soft low-pass + vinyl noise
    from numpy.fft import rfft, irfft
    seg = 1 << 20; y = np.zeros_like(out)
    for i in range(0, L, seg):
        x = out[i:i + seg]; X = rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); X *= 1 / (1 + (f / 4500) ** 2); y[i:i + len(x)] = irfft(X, len(x))
    y += 0.002 * rng.standard_normal(L)
    fade = int(3 * SR); y[:fade] *= np.linspace(0, 1, fade); y[-fade:] *= np.linspace(1, 0, fade)
    y = y / np.max(np.abs(y)) * 0.6
    st = np.stack([y, np.roll(y, int(0.012 * SR))], 1)
    sf.write(ROOT / "build" / "music.wav", st.astype(np.float32), SR)
    print("music", total)

if __name__ == "__main__":
    main()
