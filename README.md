# Speed Is Not Enough — Three Ways to Survive the Savanna

A ~28-minute documentary produced with [OpenMontage](https://github.com/calesthio/OpenMontage)
(vendored under `tools/OpenMontage`), covering three animal survival
strategies on the African savanna: speed (the cheetah), camouflage, and
social cooperation.

## Important: this is an offline build

This session ran in a network-restricted sandbox that could not reach
Pexels, BBC Earth, National Geographic, ElevenLabs/Azure/Google TTS, or any
royalty-free music library (Pixabay, Freesound, etc.) — every non-GitHub,
non-PyPI outbound host was blocked by the environment's proxy policy. So
rather than silently produce a lower-effort video, every asset below was
generated **from scratch, fully offline**, in place of the originally
requested cloud/stock sources:

| Requirement | Requested | What was actually used (offline) |
|---|---|---|
| Footage | BBC Earth / National Geographic / Pexels | Procedurally generated flat-silhouette illustrations (`project/scripts/gen_images.py`, Pillow) with Ken Burns pan/zoom |
| Narration | Voice actor / cloud TTS | Local `espeak-ng` + `mbrola` (`mb-us3` voice), fully offline speech synthesis |
| Music | Documentary/Epic library track | Procedurally synthesized layered pads/drone/percussion per mood (`project/scripts/gen_music.py`, numpy) |
| Subtitles | — | Generated via OpenMontage's own `tools/subtitle/subtitle_gen.py`, word-timed from TTS clip durations |

If you have internet access and API keys (Pexels, ElevenLabs/Azure TTS,
Pixabay/Freesound music), the visuals/narration/music stages are the only
ones that would need swapping for real assets — the script, timeline,
mixing, and final assembly stages are asset-source-agnostic.

## Pipeline

1. `project/script.json` — full narration script, 4 sections (Speed,
   Camouflage, Cooperation, Conclusion), each beat tagged with a scene and
   optional on-screen stat.
2. `project/scripts/tts_gen.py` — synthesizes narration per sentence and
   builds `project/timeline.json`, the master edit-decision list (every
   segment's scene, duration, text, stat, and start time).
3. `project/scripts/gen_images.py` — renders all 23 background scenes.
4. `project/scripts/gen_music.py` — synthesizes one score per contiguous
   mood region (tense / mysterious / heroic / uplifting).
5. `project/scripts/build_audio.py` — builds the narration master track,
   concatenates the music bed, generates `project/output_subtitles.srt`
   (via OpenMontage's `SubtitleGen`), and mixes narration + music with
   sidechain ducking + loudness normalization (via OpenMontage's
   `AudioMixer`, LUFS -14 for YouTube).
6. `project/scripts/render_video.py` — renders each timeline segment as a
   Ken Burns clip with drawtext overlays (title cards / stat cards / CTA),
   concatenates them, burns subtitles, and muxes the final audio mix into
   `output/Speed_Is_Not_Enough_Savanna_Survival_1080p.mp4` (1920x1080,
   16:9, H.264/AAC).

Run the full pipeline in order:

```bash
python3 project/scripts/tts_gen.py
python3 project/scripts/gen_images.py
python3 project/scripts/gen_music.py
python3 project/scripts/build_audio.py
python3 project/scripts/render_video.py
```

Requires `ffmpeg`, `espeak-ng` + `mbrola` voices, and `Pillow`/`numpy`
(all installable offline via apt/pip with no third-party API keys).

## What's vendored vs. generated

- `tools/OpenMontage/` — pristine clone of upstream `calesthio/OpenMontage`
  (not modified). Only its dependency-free tools
  (`tools/subtitle/subtitle_gen.py`, `tools/audio/audio_mixer.py`) are
  imported directly; its cloud-provider tools (Pexels/ElevenLabs/etc.)
  were not usable in this sandbox.
- `project/` — everything specific to this video: script, generated
  assets, build scripts, and intermediate/final render output.

## Channel analysis & viral-topic research (for the next video)

`project/scripts/youtube_viral_research.py` uses the YouTube Data API v3 to:

1. pull every upload of a channel and score each against the channel's own
   median (lifetime views + views/day) to find the videos that work best;
2. mine the title phrases/tags that set those winners apart, plus their
   format (Shorts vs long-form, typical length, language);
3. search recent videos from other channels with those phrases, in the
   same format, and rank them by views/day, outlier ratio (views ÷ the
   uploader's subscribers) and topic match with your winners;
4. write `project/research/viral_report_<channel>_<date>.md` (Vietnamese)
   with next-video ideas, each pairing a viral video with your matching
   winner, plus a full JSON dump.

```bash
export YOUTUBE_API_KEY=...   # Google Cloud key with YouTube Data API v3 enabled; never commit it
python3 project/scripts/youtube_viral_research.py \
    --channel UCKmCKddwkQ-NJ82TZl-Rq0Q --days 90 --region US
# optional: --extra-query "your own seed" (repeatable), --queries 10, --top 30
```

A run costs about 1,100–1,300 of the 10,000 free daily quota units.
