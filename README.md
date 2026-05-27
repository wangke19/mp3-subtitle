# MP3 Karaoke Subtitle Generator

Generate karaoke subtitle videos from MP3 audio + lyrics text. Outputs 1080x1080 MP4 with per-character smooth highlighting (ASS `\kf` effect).

## Features

- **WhisperX forced alignment** — lyrics text is force-aligned to audio via wav2vec2 for precise per-character timestamps
- **ASS karaoke subtitles** — smooth `\kf` highlight effect, character-by-character timing
- **Multiple background modes** — static cover, GIF animation, or multi-image crossfade slideshow
- **Chinese audio support** — optimized for Chinese (zh) with `large-v3` Whisper model

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Typical usage (lyrics auto-detected from material/{song_name}/{song_name}.txt)
python run.py material/一路向西.mp3

# With cover image
python run.py material/一路向西.mp3 --cover cover.jpg

# Multi-image slideshow background (crossfade)
python run.py material/一路向西.mp3 --bg-images material/img1.jpg material/img2.jpg material/img3.jpg

# GIF animated background
python run.py material/一路向西.mp3 --bg-images material/anim.gif

# Explicit lyrics path
python run.py material/一路向西.mp3 --lyrics other_lyrics.txt

# Without lyrics file (auto-transcribe)
python run.py material/一路向西.mp3

# With GPU acceleration
python run.py material/一路向西.mp3 --device cuda --compute-type float16
```

Output files are written to `build/{song_name}.mp4` by default.

## Directory Structure

```
material/{song_name}/
  {song_name}.mp3    — input audio
  {song_name}.txt    — lyrics (auto-detected)
  img*.jpg           — background images
  (intermediate files — transcript.json, aligned.json, karaoke.ass, etc.)

build/
  {song_name}.mp4    — final output video
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `mp3_path` | required | Input MP3 file |
| `--lyrics` | `material/{name}/{name}.txt` | Lyrics text file path (auto-detected if exists) |
| `--cover` | none | Cover image (JPG/PNG) for static background |
| `--bg-images` | none | GIF file or multiple images for slideshow |
| `--output` | `build/{name}.mp4` | Output MP4 path |
| `--model` | `large-v3` | Whisper model name |
| `--language` | `zh` | Language code |
| `--style` | `styles/default.ass` | ASS style preset file |
| `--device` | `cpu` | Compute device (cpu/cuda) |
| `--compute-type` | `int8` | Compute type (int8/float16) |
| `--offset` | `0.0` | Shift subtitles by N seconds |

## Lyrics File Format

Plain text, one line per lyrics line. Header lines (title, markers) are supported:

```
一路向西
[前奏]
黄昏的余晖 染红了车窗外的风尘
把小镇来的少年 塞进写字楼方寸的晨昏
...
```

Lines starting with `[brackets]` are treated as markers with pre-audio timing.

## How It Works

1. **Transcription** — WhisperX transcribes audio for segment boundaries and VAD
2. **Force Alignment** — Lyrics text is matched to transcript segments, then force-aligned via wav2vec2 for precise per-character timestamps. Lines in transcript gaps are proportionally interpolated.
3. **Subtitle Generation** — ASS file with `\kf` karaoke tags per character
4. **Rendering** — ffmpeg renders the final video with background + subtitle burn

## Source Code

```
src/
  transcribe.py   — WhisperX transcription and forced alignment
  align.py        — Lyrics alignment and header parsing
  subtitle.py     — ASS karaoke subtitle generation
  render.py       — ffmpeg rendering pipeline
styles/
  default.ass     — Default subtitle style preset
tests/            — Unit tests
```

## Requirements

- Python 3.12+
- ffmpeg
- whisperx >= 3.1.1

## Environment Variables

- `HF_ENDPOINT` — Hugging Face mirror URL (e.g. `https://hf-mirror.com` for China)

## License

MIT
