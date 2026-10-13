"""Synthesize narration per sentence with Kokoro (offline ONNX) and build timeline.json."""
import json, re, sys, os
from pathlib import Path
import numpy as np, soundfile as sf
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from script import SCENES
from kokoro_onnx import Kokoro

MODEL_DIR = Path(os.environ.get("KOKORO_DIR", "/home/user/models"))
VOICE, SPEED, SR = "am_michael", 1.0, 24000
GAP, TAIL, CHAPTER_TAIL = 0.30, 0.55, 0.9

def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

def main():
    k = Kokoro(str(MODEL_DIR / "kokoro-v1.0.onnx"), str(MODEL_DIR / "voices-v1.0.bin"))
    out = ROOT / "build" / "tts"; out.mkdir(parents=True, exist_ok=True)
    timeline, t, chunks = [], 0.0, []
    lead = np.zeros(int(SR * 0.6), np.float32); chunks.append(lead); t = 0.6
    for i, (vis, narr) in enumerate(SCENES):
        sc = dict(index=i, visual=vis, start=t, sentences=[])
        if i == 0:
            sc["start"] = 0.0
        for j, s in enumerate(sentences(narr)):
            wav = out / f"s{i:03d}_{j:02d}.wav"
            if wav.exists():
                a, _ = sf.read(wav, dtype="float32")
            else:
                a, sr = k.create(s, voice=VOICE, speed=SPEED, lang="en-us")
                a = a.astype(np.float32); sf.write(wav, a, sr)
            # trim leading/trailing silence
            nz = np.where(np.abs(a) > 0.01)[0]
            if len(nz): a = a[max(0, nz[0] - 600): nz[-1] + 1800]
            sc["sentences"].append(dict(text=s, start=round(t, 3), dur=round(len(a) / SR, 3)))
            chunks.append(a); t += len(a) / SR
            g = np.zeros(int(SR * GAP), np.float32); chunks.append(g); t += GAP
        tail = CHAPTER_TAIL if vis["type"] == "chapter" else TAIL
        chunks.append(np.zeros(int(SR * tail), np.float32)); t += tail
        sc["end"] = round(t, 3); sc["dur"] = round(sc["end"] - sc["start"], 3)
        timeline.append(sc)
        print(f"scene {i:02d} {vis['type']:8s} {sc['dur']:6.1f}s  total {t/60:5.2f} min", flush=True)
    chunks.append(np.zeros(int(SR * 1.5), np.float32)); t += 1.5
    timeline[-1]["end"] = round(t, 3); timeline[-1]["dur"] = round(t - timeline[-1]["start"], 3)
    narration = np.concatenate(chunks)
    sf.write(ROOT / "build" / "narration.wav", narration, SR)
    json.dump(dict(total=round(t, 3), fps=24, scenes=timeline), open(ROOT / "timeline.json", "w"), indent=1)
    print("TOTAL", t / 60, "min")

if __name__ == "__main__":
    main()
