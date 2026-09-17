#!/usr/bin/env python3
"""Stage 4: assemble the narration master track, the continuous music bed,
the SRT subtitle file, and the final ducked/normalized audio mix — reusing
OpenMontage's own audio_mixer and subtitle_gen tools (pure ffmpeg / stdlib,
no network calls) rather than reinventing them.
"""
from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "project"
OM = ROOT / "tools" / "OpenMontage"
sys.path.insert(0, str(OM))

from tools.audio.audio_mixer import AudioMixer  # noqa: E402
from tools.subtitle.subtitle_gen import SubtitleGen  # noqa: E402

NARR_SR = 16000
BUILD = PROJECT / "build"
BUILD.mkdir(parents=True, exist_ok=True)


def build_narration_master(timeline: list[dict], total_duration: float) -> Path:
    out_path = BUILD / "narration_master_16k.wav"
    n_samples = int(NARR_SR * (total_duration + 1.0))
    buf = bytearray(n_samples * 2)  # 16-bit mono silence

    for seg in timeline:
        if seg["kind"] != "narration" or not seg.get("audio"):
            continue
        wav_path = ROOT / seg["audio"]
        with wave.open(str(wav_path), "rb") as wf:
            assert wf.getframerate() == NARR_SR and wf.getnchannels() == 1
            frames = wf.readframes(wf.getnframes())
        start_sample = int(round(seg["start"] * NARR_SR))
        start_byte = start_sample * 2
        end_byte = start_byte + len(frames)
        if end_byte > len(buf):
            buf.extend(bytes(end_byte - len(buf)))
        buf[start_byte:end_byte] = frames

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(NARR_SR)
        wf.writeframes(bytes(buf))

    # Resample/upmix to match the 44.1kHz stereo music tracks so AudioMixer's
    # amix filter (which needs matching stream parameters) works cleanly.
    resampled = BUILD / "narration_master.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(out_path),
        "-ar", "44100", "-ac", "2",
        str(resampled),
    ], check=True, capture_output=True)
    return resampled


def build_music_master(manifest: list[dict], total_duration: float) -> Path:
    processed = []
    fade = 1.5
    for region in manifest:
        src = ROOT / region["path"]
        dur = region["duration"]
        out = BUILD / f"music_region_{region['index']:02d}_faded.wav"
        af = f"atrim=0:{dur},afade=t=in:d={fade},afade=t=out:st={max(0, dur - fade)}:d={fade}"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(src),
            "-af", af,
            str(out),
        ], check=True, capture_output=True)
        processed.append(out)

    concat_list = BUILD / "music_concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in processed))
    out_path = BUILD / "music_master.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-ar", "44100", "-ac", "2",
        str(out_path),
    ], check=True, capture_output=True)
    return out_path


def build_subtitles(subtitle_segments: list[dict]) -> Path:
    tool = SubtitleGen()
    out_path = PROJECT / "output_subtitles.srt"
    result = tool.execute({
        "segments": subtitle_segments,
        "format": "srt",
        "output_path": str(out_path),
        "max_words_per_cue": 7,
        "max_chars_per_line": 40,
    })
    if not result.success:
        raise RuntimeError(f"SubtitleGen failed: {result.error}")
    print("Subtitles:", result.data)
    return out_path


def main():
    data = json.loads((PROJECT / "timeline.json").read_text())
    timeline = data["timeline"]
    total_duration = data["total_duration"]
    manifest = json.loads((PROJECT / "music_manifest.json").read_text())

    print("Building narration master...")
    narration_path = build_narration_master(timeline, total_duration)

    print("Building music master...")
    music_path = build_music_master(manifest, total_duration)

    print("Building subtitles...")
    build_subtitles(data["subtitle_segments"])

    print("Mixing narration + music with ducking...")
    mixer = AudioMixer()
    result = mixer.execute({
        "operation": "full_mix",
        "tracks": [
            {"path": str(narration_path), "role": "speech"},
            {"path": str(music_path), "role": "music", "volume": 0.42},
        ],
        "ducking": {
            "enabled": True,
            "music_volume_during_speech": 0.16,
            "attack_ms": 250,
            "release_ms": 700,
        },
        "normalize": True,
        "loudnorm_target": -14,
        "target_duration": total_duration,
        "output_path": str(BUILD / "final_audio_mix.wav"),
    })
    if not result.success:
        raise RuntimeError(f"AudioMixer failed: {result.error}")
    print("Final mix:", result.data)


if __name__ == "__main__":
    main()
