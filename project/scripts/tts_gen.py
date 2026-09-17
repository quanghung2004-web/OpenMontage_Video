#!/usr/bin/env python3
"""Stage 1: synthesize offline narration (espeak-ng/mbrola) and build the
master timeline (timeline.json) that drives every later render stage.

No network access is used anywhere in this script — narration is fully
local text-to-speech, since cloud TTS providers are unreachable from this
sandbox.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "project"
NARR_DIR = PROJECT / "assets" / "audio" / "narration"
NARR_DIR.mkdir(parents=True, exist_ok=True)

VOICE = "mb-us3"       # offline mbrola male voice — documentary narrator tone
TTS_SPEED = 118        # words/min target passed to espeak-ng (-s)
PITCH = 40

SENT_PAUSE = 0.50      # silence after each sentence
BEAT_EXTRA_PAUSE = 0.35  # additional silence after the last sentence of a beat
SECTION_EXTRA_PAUSE = 1.0  # additional silence after a section's last beat

TITLE_CARD_DURATION = 4.5
INTRO_BUMPER_DURATION = 3.0
END_CARD_HOLD = 5.0
INTERLUDE_DURATION = 17.0

# Mid-section interlude inserted after this many beats into speed/camouflage/cooperation
MID_INTERLUDE_AFTER_BEAT_FRACTION = 0.5


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def synth(text: str, out_path: Path) -> float:
    """Synthesize one sentence with espeak-ng/mbrola, return duration in seconds."""
    cmd = [
        "espeak-ng",
        "-v", VOICE,
        "-s", str(TTS_SPEED),
        "-p", str(PITCH),
        "-g", "6",  # gap between words (10ms units) for clearer diction
        text,
        "-w", str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(out_path)],
        check=True, capture_output=True, text=True,
    )
    return float(probe.stdout.strip())


def word_timestamps(words: list[str], start: float, duration: float) -> list[dict]:
    """Evenly distribute a sentence's audio duration across its words,
    weighted by word length, for approximate but reasonable subtitle sync."""
    weights = [max(1, len(w)) for w in words]
    total_w = sum(weights)
    out = []
    t = start
    for w, wt in zip(words, weights):
        dur = duration * (wt / total_w)
        out.append({"word": w, "start": round(t, 3), "end": round(t + dur, 3)})
        t += dur
    return out


def main() -> None:
    script = json.loads((PROJECT / "script.json").read_text())

    timeline: list[dict] = []
    subtitle_segments: list[dict] = []
    t = 0.0

    # Intro bumper (silent, brand card)
    timeline.append({
        "kind": "bumper", "scene": "intro_bumper", "duration": INTRO_BUMPER_DURATION,
        "text": None, "audio": None, "start": t, "mood": "tense",
    })
    t += INTRO_BUMPER_DURATION

    sections = script["sections"]
    for s_idx, section in enumerate(sections):
        # Section title card
        timeline.append({
            "kind": "title", "scene": "title_card", "duration": TITLE_CARD_DURATION,
            "text": section["display_title"], "audio": None, "start": t,
            "mood": section["mood"],
        })
        t += TITLE_CARD_DURATION

        # Establishing interlude right after the title card
        timeline.append({
            "kind": "interlude", "scene": section["beats"][0]["scene"],
            "duration": INTERLUDE_DURATION, "text": None, "audio": None, "start": t,
            "mood": section["mood"],
        })
        t += INTERLUDE_DURATION

        beats = section["beats"]
        mid_point = max(1, int(len(beats) * MID_INTERLUDE_AFTER_BEAT_FRACTION))

        for b_idx, beat in enumerate(beats):
            sentences = split_sentences(beat["text"])
            for sent_idx, sentence in enumerate(sentences):
                fname = f"s{s_idx:02d}_b{b_idx:02d}_w{sent_idx:02d}.wav"
                wav_path = NARR_DIR / fname
                dur = synth(sentence, wav_path)

                words = sentence.split()
                wts = word_timestamps(words, t, dur)
                subtitle_segments.append({
                    "text": sentence,
                    "start": t,
                    "end": t + dur,
                    "words": wts,
                })

                is_last_sentence = sent_idx == len(sentences) - 1
                pause = SENT_PAUSE
                if is_last_sentence:
                    pause += BEAT_EXTRA_PAUSE

                timeline.append({
                    "kind": "narration",
                    "scene": beat["scene"],
                    "duration": dur + pause,
                    "speech_duration": dur,
                    "text": sentence,
                    "audio": str(wav_path.relative_to(ROOT)),
                    "start": t,
                    "stat": beat.get("stat") if is_last_sentence else None,
                    "mood": section["mood"],
                })
                t += dur + pause

            # Mid-section interlude after roughly half the beats (skip on cold_open/conclusion which are short)
            if b_idx == mid_point - 1 and len(beats) >= 6:
                timeline.append({
                    "kind": "interlude", "scene": beat["scene"],
                    "duration": INTERLUDE_DURATION * 0.7, "text": None, "audio": None,
                    "start": t, "mood": section["mood"],
                })
                t += INTERLUDE_DURATION * 0.7

        t += SECTION_EXTRA_PAUSE

    # End card hold (CTA / subscribe emphasis)
    timeline.append({
        "kind": "endcard", "scene": "cta_card", "duration": END_CARD_HOLD,
        "text": "SUBSCRIBE FOR MORE", "audio": None, "start": t,
        "mood": "uplifting",
    })
    t += END_CARD_HOLD

    total_duration = t

    out = {
        "title": script["title"],
        "total_duration": total_duration,
        "timeline": timeline,
        "subtitle_segments": subtitle_segments,
    }
    (PROJECT / "timeline.json").write_text(json.dumps(out, indent=2))

    mins = int(total_duration // 60)
    secs = int(total_duration % 60)
    print(f"Timeline built: {len(timeline)} segments, {len(subtitle_segments)} narration sentences")
    print(f"Total duration: {mins}m {secs}s ({total_duration:.1f}s)")


if __name__ == "__main__":
    main()
