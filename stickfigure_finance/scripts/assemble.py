"""Mix narration + ducked music, write SRT, concat segments, mux final MP4."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render import caption_chunks

def ts(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"

def run(cmd):
    print(" ".join(map(str, cmd))[:200]); subprocess.run(cmd, check=True)

def main():
    tl = json.load(open(ROOT / "timeline.json"))
    b = ROOT / "build"
    # subtitles
    lines, n = [], 1
    for sc in tl["scenes"]:
        for a, e, s in caption_chunks(sc["sentences"]):
            lines.append(f"{n}\n{ts(a)} --> {ts(e)}\n{s}\n"); n += 1
    (ROOT / "subtitles_en.srt").write_text("\n".join(lines))
    # audio mix: music ducked under voice, loudness normalized for YouTube (-14 LUFS)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", b / "narration.wav", "-i", b / "music.wav", "-filter_complex",
         "[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[v][sc];"
         "[1:a]aresample=48000,volume=0.32[m];"
         "[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=600[md];"
         "[v][md]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[out]",
         "-map", "[out]", "-c:a", "pcm_s16le", b / "mix.wav"])
    segs = sorted((b / "segments").glob("seg_*.mp4"))
    assert len(segs) == len(tl["scenes"]), (len(segs), len(tl["scenes"]))
    (b / "concat.txt").write_text("".join(f"file '{p}'\n" for p in segs))
    out = ROOT.parent / "output" / "The_Money_Trap_StickFigure_Finance_1080p.mp4"
    out.parent.mkdir(exist_ok=True)
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", b / "concat.txt", "-i", b / "mix.wav",
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
         "-movflags", "+faststart", out])
    print("wrote", out)

if __name__ == "__main__":
    main()
