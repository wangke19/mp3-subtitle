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

import whisperx

sys.path.insert(0, str(Path(__file__).parent))

from src.transcribe import load_alignment_model, force_align_lyrics
from src.align import align_force, align_lyrics, _parse_lyrics_with_header
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
    args = parser.parse_args()

    if not Path(args.mp3_path).exists():
        parser.error(f"MP3 file not found: {args.mp3_path}")

    temp_dir = args.temp_dir or tempfile.mkdtemp(prefix="mp3karaoke-")
    Path(temp_dir).mkdir(parents=True, exist_ok=True)

    audio = whisperx.load_audio(args.mp3_path)

    if args.lyrics and Path(args.lyrics).exists():
        _run_force_align_pipeline(args, audio, temp_dir)
    else:
        _run_transcribe_pipeline(args, audio, temp_dir)


def _run_force_align_pipeline(args, audio, temp_dir):
    """New pipeline: VAD → force-align lyrics text directly."""
    print("[1/3] Detecting voice activity and transcribing for VAD boundaries...")

    # Step 1: Run Whisper transcription to get VAD segment boundaries
    # (We only need rough timing, not the actual text)
    model = whisperx.load_model(
        args.model, args.device, compute_type=args.compute_type,
        language=args.language,
        asr_options={"word_timestamps": True, "condition_on_previous_text": False},
    )
    result = model.transcribe(audio, batch_size=8, language=args.language)
    del model

    vad_segments = [{"start": seg["start"], "end": seg["end"]} for seg in result["segments"]]
    print(f"  → {len(vad_segments)} VAD segments, {vad_segments[0]['start']:.1f}s - {vad_segments[-1]['end']:.1f}s")

    # Save transcript for debugging
    transcript_path = str(Path(temp_dir) / "transcript.json")
    json.dump(result, open(transcript_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # Step 2: Force-align lyrics text directly
    print("[2/3] Force-aligning lyrics text to audio...")
    header_lines, body_lines = _parse_lyrics_with_header(args.lyrics)

    align_model, align_metadata = load_alignment_model(
        language=args.language, device=args.device
    )

    aligned_lines = force_align_lyrics(
        audio=audio,
        lyrics_lines=body_lines,
        vad_segments=vad_segments,
        align_model=align_model,
        align_metadata=align_metadata,
        device=args.device,
    )
    del align_model

    first_audio_time = vad_segments[0]["start"] if vad_segments else 0
    aligned = align_force(aligned_lines, header_lines, first_audio_time)

    matched = sum(1 for l in aligned["lines"] if "warning" not in l)
    print(f"  → {len(aligned['lines'])} lines ({matched} aligned, {len(aligned['lines']) - matched} interpolated)")

    aligned_path = str(Path(temp_dir) / "aligned.json")
    Path(aligned_path).write_text(json.dumps(aligned, ensure_ascii=False, indent=2), encoding="utf-8")

    # Step 3: Generate ASS + render
    _generate_and_render(args, aligned, temp_dir)


def _run_transcribe_pipeline(args, audio, temp_dir):
    """Legacy pipeline: transcribe → fuzzy match → subtitle (no lyrics file)."""
    from src.transcribe import transcribe
    from src.align import align_lyrics as legacy_align

    print("[1/4] Transcribing (no lyrics provided, using raw transcript)...")

    transcript = transcribe(
        args.mp3_path, model_name=args.model, language=args.language,
        device=args.device, compute_type=args.compute_type,
    )

    aligned = _transcript_to_aligned(transcript)
    _generate_and_render(args, aligned, temp_dir)


def _generate_and_render(args, aligned, temp_dir):
    """Generate ASS subtitles and render final video."""
    ass_path = str(Path(temp_dir) / "karaoke.ass")
    print("[3/3] Generating ASS karaoke subtitles and rendering...")
    ass_content = generate_ass(aligned, style_path=args.style, offset=args.offset)
    Path(ass_path).write_text(ass_content, encoding="utf-8")

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
