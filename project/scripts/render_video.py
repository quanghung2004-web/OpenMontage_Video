#!/usr/bin/env python3
"""Stage 5: render every timeline segment as a Ken-Burns video clip with
drawtext overlays (titles / stat cards / CTA), concatenate them, then burn
subtitles and mux the final audio mix into a 1080p H.264 MP4.

Pure ffmpeg — no network, no external renderer (Remotion/Node were not an
option here since this pipeline has no cloud assets to composite; a plain
ffmpeg runtime is the correct, explicit choice for a slideshow-style
documentary edit, matching OpenMontage's own documented ffmpeg-fallback
render path).
"""
from __future__ import annotations

import json
import multiprocessing
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "project"
IMAGES = PROJECT / "assets" / "images"
BUILD = PROJECT / "build"
SEGMENTS_DIR = BUILD / "segments"
SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
TEXT_DIR = BUILD / "text"
TEXT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FPS = 24
W, H = 1920, 1080
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

SERIES_TITLE = "SPEED IS NOT ENOUGH"
SERIES_SUB = "Three Ways to Survive the Savanna"


def write_text(key: str, text: str) -> Path:
    p = TEXT_DIR / f"{key}.txt"
    p.write_text(text)
    return p


def esc_colon(path: Path) -> str:
    # ffmpeg filter option values use ':' as a sub-separator; escape any
    # that appear in filesystem paths (none expected here, but be safe).
    return str(path).replace(":", "\\:")


def zoompan_filter(duration: float, variant: int) -> str:
    if variant == 0:
        zexpr = "min(zoom+0.0011,1.16)"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif variant == 1:
        zexpr = "min(zoom+0.0011,1.18)"
        x, y = "iw/2-(iw/zoom/2)-40*sin(on/200)", "ih/2-(ih/zoom/2)"
    elif variant == 2:
        zexpr = "min(zoom+0.0009,1.14)"
        x, y = "iw/2-(iw/zoom/2)+30*sin(on/220)", "ih/2-(ih/zoom/2)-20"
    else:
        zexpr = "if(lte(zoom,1.0),1.16,max(1.0,zoom-0.0011))"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    return (
        f"zoompan=z='{zexpr}':d=1:x='{x}':y='{y}':s={W}x{H}:fps={FPS}"
    )


def build_overlay_filters(seg: dict, duration: float) -> tuple[list[str], list[str]]:
    """Returns (filter_lines, input_args) for drawtext overlays on this segment."""
    filters = []
    inputs = []
    fade = min(0.5, duration / 4)

    def fade_alpha(dur):
        return f"if(lt(t,{fade}),t/{fade},if(gt(t,{dur - fade}),({dur}-t)/{fade},1))"

    if seg["kind"] == "title":
        title_txt = write_text(f"title_{seg['start']:.2f}", seg["text"])
        series_txt = write_text(f"series_{seg['start']:.2f}", SERIES_TITLE)
        filters.append(
            f"drawtext=fontfile={FONT_REG}:textfile='{esc_colon(series_txt)}':"
            f"fontsize=34:fontcolor=white@0.85:borderw=2:bordercolor=black@0.6:"
            f"x=(w-text_w)/2:y=h*0.34:alpha='{fade_alpha(duration)}'"
        )
        filters.append(
            f"drawtext=fontfile={FONT_BOLD}:textfile='{esc_colon(title_txt)}':"
            f"fontsize=76:fontcolor=white:borderw=3:bordercolor=black@0.7:"
            f"x=(w-text_w)/2:y=h*0.42:alpha='{fade_alpha(duration)}'"
        )
    elif seg["kind"] == "bumper":
        t1 = write_text("bumper1", "AN OPENMONTAGE NATURE DOCUMENTARY")
        filters.append(
            f"drawtext=fontfile={FONT_BOLD}:textfile='{esc_colon(t1)}':"
            f"fontsize=42:fontcolor=white:borderw=2:bordercolor=black@0.6:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:alpha='{fade_alpha(duration)}'"
        )
    elif seg["kind"] == "endcard":
        t1 = write_text("end1", "SUBSCRIBE")
        t2 = write_text("end2", "for more deep dives into the natural world")
        filters.append(
            f"drawbox=x='(iw-560)/2':y='ih*0.44':w=560:h=120:color=black@0.55:t=fill"
        )
        filters.append(
            f"drawtext=fontfile={FONT_BOLD}:textfile='{esc_colon(t1)}':"
            f"fontsize=64:fontcolor=white:x=(w-text_w)/2:y=h*0.46"
        )
        filters.append(
            f"drawtext=fontfile={FONT_REG}:textfile='{esc_colon(t2)}':"
            f"fontsize=30:fontcolor=white@0.9:borderw=2:bordercolor=black@0.6:"
            f"x=(w-text_w)/2:y=h*0.58"
        )
    elif seg.get("stat"):
        stat = seg["stat"]
        label_p = write_text(f"stat_label_{seg['start']:.2f}", stat["label"].upper())
        value_p = write_text(f"stat_value_{seg['start']:.2f}", stat["value"])
        sub_p = write_text(f"stat_sub_{seg['start']:.2f}", stat.get("sublabel", ""))
        box_w, box_x, box_y, box_h = 620, 60, H - 380, 210
        filters.append(
            f"drawbox=x={box_x}:y={box_y}:w={box_w}:h={box_h}:color=black@0.55:t=fill:"
            f"enable='between(t,0,{duration})'"
        )
        filters.append(
            f"drawbox=x={box_x}:y={box_y}:w=8:h={box_h}:color=0xE8A23C@0.95:t=fill"
        )
        filters.append(
            f"drawtext=fontfile={FONT_BOLD}:textfile='{esc_colon(label_p)}':"
            f"fontsize=26:fontcolor=0xE8A23C:x={box_x + 34}:y={box_y + 28}"
        )
        filters.append(
            f"drawtext=fontfile={FONT_BOLD}:textfile='{esc_colon(value_p)}':"
            f"fontsize=52:fontcolor=white:x={box_x + 34}:y={box_y + 68}"
        )
        filters.append(
            f"drawtext=fontfile={FONT_REG}:textfile='{esc_colon(sub_p)}':"
            f"fontsize=24:fontcolor=white@0.85:x={box_x + 34}:y={box_y + 150}:"
            f"line_spacing=6"
        )
    return filters, inputs


def render_segment(idx: int, seg: dict) -> Path:
    scene = seg["scene"]
    img_path = IMAGES / f"{scene}.png"
    duration = seg["duration"]
    out_path = SEGMENTS_DIR / f"seg_{idx:04d}.mp4"
    if out_path.exists():
        return out_path

    variant = (idx * 7 + len(scene)) % 4
    vf_parts = [zoompan_filter(duration, variant), "format=yuv420p"]
    overlay_filters, _ = build_overlay_filters(seg, duration)
    vf_parts.extend(overlay_filters)
    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(FPS), "-loop", "1", "-t", f"{duration:.3f}", "-i", str(img_path),
        "-vf", vf,
        "-r", str(FPS),
        "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def main():
    data = json.loads((PROJECT / "timeline.json").read_text())
    timeline = data["timeline"]
    total_duration = data["total_duration"]

    print(f"Rendering {len(timeline)} segments with {multiprocessing.cpu_count()} workers...")
    with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as ex:
        futures = [ex.submit(render_segment, i, seg) for i, seg in enumerate(timeline)]
        paths = [f.result() for f in futures]

    concat_list = BUILD / "segments_concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))

    silent_full = BUILD / "silent_full.mp4"
    print("Concatenating segments (stream copy)...")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy",
        str(silent_full),
    ], check=True, capture_output=True)

    srt_path = PROJECT / "output_subtitles.srt"
    audio_path = BUILD / "final_audio_mix.wav"
    final_path = OUTPUT_DIR / "Speed_Is_Not_Enough_Savanna_Survival_1080p.mp4"

    print("Final encode: burning subtitles + muxing audio...")
    sub_style = (
        "FontName=DejaVu Sans,FontSize=15,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
        "MarginV=80,Alignment=2"
    )
    vf = f"subtitles={esc_colon(srt_path)}:force_style='{sub_style}'"

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-stats",
        "-i", str(silent_full),
        "-i", str(audio_path),
        "-vf", vf,
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", f"{total_duration:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(final_path),
    ]
    subprocess.run(cmd, check=True)
    print("DONE:", final_path)


if __name__ == "__main__":
    main()
