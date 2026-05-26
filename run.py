"""MP3 Karaoke Subtitle Generator — CLI entry point.

Usage:
    python run.py song.mp3 --cover cover.jpg --lyrics lyrics.txt
    python run.py song.mp3 --lyrics lyrics.txt --output my_video.mp4
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.transcribe import transcribe
from src.align import align_lyrics
from src.subtitle import generate_ass
from src.render import render


def main():
    parser = argparse.ArgumentParser(
        description="Generate karaoke subtitle video from MP3 + lyrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("mp3_path", help="Path to input MP3 file")
    parser.add_argument("--cover", default=None, help="Path to cover image (JPG/PNG)")
    parser.add_argument("--lyrics", default=None, help="Path to lyrics text file")
    parser.add_argument("--output", default="output.mp4", help="Output MP4 path")
    parser.add_argument("--model", default="large-v3", help="Whisper model name")
    parser.add_argument("--language", default="zh", help="Language code")
    parser.add_argument("--style", default=None, help="ASS style preset file path")
    parser.add_argument("--temp-dir", default=None, help="Temp directory for intermediate files")
    parser.add_argument("--device", default="cpu", help="Compute device (cpu/cuda)")
    parser.add_argument("--compute-type", default="int8", help="Compute type (int8/float16)")
    parser.add_argument("--offset", type=float, default=0.0, help="Shift subtitles by N seconds (positive=later)")
    parser.add_argument("--initial-prompt", default=None, help="Initial prompt to guide WhisperX transcription")
    args = parser.parse_args()

    if not Path(args.mp3_path).exists():
        parser.error(f"MP3 file not found: {args.mp3_path}")

    temp_dir = args.temp_dir or tempfile.mkdtemp(prefix="mp3karaoke-")
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    print(f"[1/4] Working directory: {temp_dir}")

    # Stage 1: Transcribe
    transcript_path = str(Path(temp_dir) / "transcript.json")
    print(f"[1/4] Transcribing {args.mp3_path} with {args.model}...")
    transcript = transcribe(
        args.mp3_path,
        model_name=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
        initial_prompt=args.initial_prompt,
    )
    Path(transcript_path).write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  → {len(transcript['segments'])} segments, saved to {transcript_path}")

    # Stage 2: Align lyrics (or skip)
    aligned_path = str(Path(temp_dir) / "aligned.json")
    if args.lyrics:
        if not Path(args.lyrics).exists():
            parser.error(f"Lyrics file not found: {args.lyrics}")
        print(f"[2/4] Aligning lyrics from {args.lyrics}...")
        aligned = align_lyrics(transcript, args.lyrics)
    else:
        print("[2/4] No lyrics provided, using raw transcript as lyrics...")
        aligned = _transcript_to_aligned(transcript)

    Path(aligned_path).write_text(
        json.dumps(aligned, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  → {len(aligned['lines'])} lines, saved to {aligned_path}")

    # Stage 3: Generate ASS
    ass_path = str(Path(temp_dir) / "karaoke.ass")
    print("[3/4] Generating ASS karaoke subtitles...")
    ass_content = generate_ass(aligned, style_path=args.style, offset=args.offset)
    if args.offset:
        print(f"  → offset applied: +{args.offset}s")
    Path(ass_path).write_text(ass_content, encoding="utf-8")
    print(f"  → {ass_path}")

    # Stage 4: Render
    print("[4/4] Rendering video...")
    output = render(
        mp3_path=args.mp3_path,
        ass_path=ass_path,
        output_path=args.output,
        cover_path=args.cover,
        temp_dir=temp_dir,
    )
    print(f"Done! Video saved to {output}")


def _transcript_to_aligned(transcript: dict) -> dict:
    """Convert raw transcript to aligned format (no lyrics mapping)."""
    lines = []
    line_no = 0
    for seg in transcript["segments"]:
        if not seg["chars"]:
            continue
        line_no += 1
        lines.append({
            "line_no": line_no,
            "text": seg["text"],
            "start": seg["start"],
            "end": seg["end"],
            "chars": seg["chars"],
        })
    return {"lines": lines}


if __name__ == "__main__":
    main()
