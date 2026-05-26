"""WhisperX transcription and forced alignment for Chinese audio."""

import json
from pathlib import Path

import whisperx
import numpy as np


def transcribe(
    mp3_path: str,
    model_name: str = "large-v3",
    language: str = "zh",
    device: str = "cpu",
    compute_type: str = "int8",
    batch_size: int = 8,
    initial_prompt: str = None,
) -> dict:
    """Transcribe audio and return character-level timestamps.

    Returns dict with 'segments' key, each segment has 'start', 'end', 'text', 'chars'.
    """
    audio = whisperx.load_audio(mp3_path)

    asr_opts = {"word_timestamps": True, "condition_on_previous_text": True}
    if initial_prompt:
        asr_opts["initial_prompt"] = initial_prompt

    model = whisperx.load_model(
        model_name,
        device,
        compute_type=compute_type,
        language=language,
        asr_options=asr_opts,
    )
    result = model.transcribe(audio, batch_size=batch_size, language=language)
    del model

    model_a, metadata = whisperx.load_align_model(
        language_code=language, device=device
    )
    result = whisperx.align(
        result["segments"],
        model_a,
        metadata,
        audio,
        device,
        return_char_alignments=True,
    )
    del model_a

    output = {"segments": []}
    for seg in result["segments"]:
        chars = []
        for word in seg.get("words", []):
            if "start" in word and "end" in word:
                chars.append(
                    {
                        "char": word["word"],
                        "start": round(word["start"], 3),
                        "end": round(word["end"], 3),
                    }
                )
        output["segments"].append(
            {
                "start": round(seg["start"], 3),
                "end": round(seg["end"], 3),
                "text": seg["text"].strip(),
                "chars": chars,
            }
        )

    return output


def load_alignment_model(
    language: str = "zh",
    device: str = "cpu",
):
    """Load the wav2vec2 alignment model. Returns (model, metadata)."""
    return whisperx.load_align_model(language_code=language, device=device)


def force_align_lyrics(
    audio: np.ndarray,
    lyrics_lines: list[str],
    vad_segments: list[dict],
    align_model,
    align_metadata: dict,
    device: str = "cpu",
) -> list[dict]:
    """Force-align lyrics text directly to audio using wav2vec2.

    This bypasses transcription text matching entirely — we pass the CORRECT
    lyrics text to the aligner and get precise character timestamps.

    Args:
        audio: numpy audio array from whisperx.load_audio()
        lyrics_lines: list of lyrics text lines (without markers)
        vad_segments: rough time boundaries from transcription,
                      list of {"start": float, "end": float}
        align_model: loaded wav2vec2 model from load_alignment_model()
        align_metadata: metadata from load_alignment_model()
        device: "cpu" or "cuda"

    Returns:
        list of {"text": str, "start": float, "end": float,
                 "chars": [{"char": str, "start": float, "end": float}]}
    """
    n_lines = len(lyrics_lines)
    n_segs = len(vad_segments)
    results = []

    # Map each lyrics line to a rough time window using VAD segments
    # Simple strategy: distribute lyrics lines proportionally across VAD segments
    # based on text length
    total_text_len = sum(len(l) for l in lyrics_lines)
    if total_text_len == 0:
        return []

    total_audio_dur = vad_segments[-1]["end"] - vad_segments[0]["start"] if vad_segments else 0
    line_start = vad_segments[0]["start"] if vad_segments else 0

    for i, line_text in enumerate(lyrics_lines):
        # Estimate duration proportional to text length
        line_ratio = len(line_text) / total_text_len if total_text_len > 0 else 1 / n_lines
        line_dur = total_audio_dur * line_ratio
        line_end = line_start + line_dur

        # Create a fake segment with the correct lyrics text
        segment = {
            "start": line_start,
            "end": line_end,
            "text": line_text,
        }

        # Run forced alignment on this single segment
        try:
            aligned = whisperx.align(
                [segment],
                align_model,
                align_metadata,
                audio,
                device,
                return_char_alignments=True,
            )

            chars = []
            seg = aligned["segments"][0] if aligned["segments"] else None

            if seg:
                # Try chars first (return_char_alignments=True), then words
                raw_items = seg.get("chars", []) or seg.get("words", [])
                for item in raw_items:
                    start_val = item.get("start")
                    end_val = item.get("end")
                    if start_val is not None and end_val is not None:
                        char_text = item.get("char", item.get("word", ""))
                        chars.append({
                            "char": char_text,
                            "start": round(float(start_val), 3),
                            "end": round(float(end_val), 3),
                        })

            if chars:
                results.append({
                    "text": line_text,
                    "start": chars[0]["start"],
                    "end": chars[-1]["end"],
                    "chars": chars,
                })
                # Next line starts where this one ends
                line_start = chars[-1]["end"] + 0.05
            else:
                # Alignment failed — use interpolated timing
                results.append({
                    "text": line_text,
                    "start": round(line_start, 3),
                    "end": round(line_end, 3),
                    "chars": _interpolate(line_text, line_start, line_end),
                    "warning": "alignment_failed",
                })
                line_start = line_end + 0.05

        except Exception as e:
            results.append({
                "text": line_text,
                "start": round(line_start, 3),
                "end": round(line_end, 3),
                "chars": _interpolate(line_text, line_start, line_end),
                "warning": f"alignment_error: {e}",
            })
            line_start = line_end + 0.05

    return results


def _interpolate(text: str, start: float, end: float) -> list[dict]:
    """Evenly distribute char timings across the given span."""
    if not text:
        return []
    n = len(text)
    duration = (end - start) / n
    return [
        {"char": c, "start": round(start + i * duration, 3), "end": round(start + (i + 1) * duration, 3)}
        for i, c in enumerate(text)
    ]


def main():
    """CLI: transcribe <mp3_path> [--model large-v3] [--language zh] [--output transcript.json]"""
    import argparse

    parser = argparse.ArgumentParser(description="WhisperX transcription")
    parser.add_argument("mp3_path", help="Path to MP3 file")
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--output", default="transcript.json")
    args = parser.parse_args()

    result = transcribe(args.mp3_path, model_name=args.model, language=args.language)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Transcript saved to {args.output}")


if __name__ == "__main__":
    main()
