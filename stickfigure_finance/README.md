# The Money Trap — stickfigure-finance-explainer

A ~20-minute (19m57s) stick-figure personal-finance explainer produced with
the **`stickfigure-finance-explainer`** playbook for OpenMontage
([`stickfigure-finance-explainer.yaml`](stickfigure-finance-explainer.yaml) — copy it
into `tools/OpenMontage/styles/`; it validates with OpenMontage's own
`styles/playbook_loader.py`).

## About the topic

The brief asked for a video about the topic of
`https://www.youtube.com/watch?v=n1DXp7Y3xA4`. This sandbox could not reach YouTube
or any mirror/oEmbed service (proxy policy denied them), and web search returned
nothing for that video ID. So the topic could not be confirmed. Following the
"don't stop to ask" instruction, the video covers the core subject of the
stick-figure finance genre: **why working harder doesn't make you rich, and
what does**: lifestyle inflation, inflation, debt, compound interest, assets
vs. liabilities, index funds and fees, and a simple plan. If the source video is
about something else, only `script.py` needs to change. The rest of the pipeline
is topic-agnostic.

## Pipeline (fully offline after model download)

| Stage | File | Notes |
|---|---|---|
| Script | `script.py` | 72 scenes, ~3,000 words, each scene = visual spec + narration. All figures pre-computed (see docstring). |
| Voice | `scripts/tts.py` | [Kokoro-82M](https://github.com/thewh1teagle/kokoro-onnx) ONNX, voice `am_michael`, per-sentence synthesis → `timeline.json` |
| Music | `scripts/music.py` | Procedural lo-fi bed (numpy): Rhodes-like chords, bass, brushed drums |
| Visuals | `scripts/render.py` | Procedural cairo renderer: hand-drawn ink stick figures (Sam & Alex) with line boil, ~25 props, animated line/bar/pie charts, stat counters, chapter cards, burned captions, progress bar. One H.264 segment per scene, rendered in parallel |
| Assembly | `scripts/assemble.py` | Writes `subtitles_en.srt`; music side-chain ducked under voice, loudnorm -14 LUFS; concat + mux → `output/The_Money_Trap_StickFigure_Finance_1080p.mp4` |

```bash
pip install kokoro-onnx soundfile pycairo numpy
# model files from the kokoro-onnx GitHub release "model-files-v1.0" into $KOKORO_DIR (default /home/user/models)
# fonts: Patrick Hand + Permanent Marker (google/fonts, OFL) installed into ~/.fonts
python3 stickfigure_finance/scripts/tts.py
python3 stickfigure_finance/scripts/music.py
python3 stickfigure_finance/scripts/render.py      # JOBS=4 by default
python3 stickfigure_finance/scripts/assemble.py
python3 stickfigure_finance/scripts/render.py preview <scene> <sec> out.png   # single-frame preview
```

The final MP4 is git-ignored (`/output/`) because of its size; it is delivered directly.
