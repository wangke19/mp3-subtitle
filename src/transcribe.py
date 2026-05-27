"""WhisperX transcription and forced alignment for Chinese audio."""

import json
from difflib import SequenceMatcher
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


def _match_segment(line_text: str, transcript_segments: list[dict]) -> int:
    """Find the best matching transcript segment for a lyrics line.

    Matches using the end portion of the lyrics line (last half), because:
    - A lyrics line can span across transcript segments
    - The end of the line determines where the next line starts
    - Using the end portion ensures we pick the segment that covers
      the latter part of the line for correct window_end estimation.

    Uses "coverage" metric: fraction of lyrics chars found in the segment,
    which works better than SequenceMatcher.ratio() for short-vs-long text.
    """
    end_portion = line_text[len(line_text) // 2:]
    if not end_portion:
        return 0

    best_idx = 0
    best_score = 0.0
    for i, seg in enumerate(transcript_segments):
        seg_text = seg.get("text", "")
        if not seg_text:
            continue
        sm = SequenceMatcher(None, end_portion, seg_text)
        coverage = sum(m.size for m in sm.get_matching_blocks()) / len(end_portion)
        if coverage > best_score:
            best_score = coverage
            best_idx = i
    return best_idx


def force_align_lyrics(
    audio: np.ndarray,
    lyrics_lines: list[str],
    transcript_segments: list[dict],
    align_model,
    align_metadata: dict,
    device: str = "cpu",
) -> list[dict]:
    """Force-align lyrics text directly to audio using wav2vec2.

    Two-phase approach:
    1. Text matching: assign each lyrics line to the best transcript segment
       (handles cases where one long segment covers multiple lines)
    2. Force alignment: use prev_end for window_start, assigned segment's
       end for window_end — ensures continuity and correct segment boundaries

    Args:
        audio: numpy audio array from whisperx.load_audio()
        lyrics_lines: list of lyrics text lines (without markers)
        transcript_segments: WhisperX transcript segments with 'text', 'start', 'end'
        align_model: loaded wav2vec2 model from load_alignment_model()
        align_metadata: metadata from load_alignment_model()
        device: "cpu" or "cuda"

    Returns:
        list of {"text": str, "start": float, "end": float,
                 "chars": [{"char": str, "start": float, "end": float}]}
    """
    if not lyrics_lines:
        return []

    # Skip short segments that are likely watermarks/noise
    start_seg = 0
    for i, seg in enumerate(transcript_segments):
        duration = float(seg["end"]) - float(seg["start"])
        text = seg.get("text", "").strip()
        if duration > 8.0 and len(text) > 5:
            start_seg = i
            break

    # Phase 1: compute match quality for each line
    line_quality = []
    for line_text in lyrics_lines:
        end_portion = line_text[len(line_text) // 2:]
        if not end_portion:
            line_quality.append(0.0)
            continue
        best_cov = 0.0
        for seg in transcript_segments:
            sm = SequenceMatcher(None, end_portion, seg.get("text", ""))
            cov = sum(m.size for m in sm.get_matching_blocks()) / len(end_portion)
            best_cov = max(best_cov, cov)
        line_quality.append(best_cov)

    # Phase 2: force-align, handling transcript gaps with proportional distribution
    prev_end = float(transcript_segments[start_seg]["start"])
    results = []
    i = 0

    while i < len(lyrics_lines):
        line_text = lyrics_lines[i]
        if not line_text:
            i += 1
            continue

        if line_quality[i] >= 0.2:
            # Well-matched line — force align normally
            seg_idx = _match_segment(line_text, transcript_segments)
            seg_idx = max(seg_idx, start_seg)
            seg = transcript_segments[seg_idx]

            window_start = prev_end + 0.05
            window_end = float(seg["end"]) + 1.0

            est_dur = max(len(line_text) * 0.35, 3.0)
            if window_end - window_start < 2.0:
                window_end = window_start + max(est_dur, 3.0)

            result = _align_one(audio, line_text, window_start, window_end,
                                align_model, align_metadata, device)
            results.append(result)
            prev_end = result["end"]
            i += 1
        else:
            # Poor match — collect consecutive gap lines
            gap_start_idx = i
            while i < len(lyrics_lines) and line_quality[i] < 0.2:
                i += 1
            gap_end_idx = i  # first well-matched line after the gap

            # Find the ceiling: start time of the next well-matched line's segment
            if gap_end_idx < len(lyrics_lines):
                ceiling_seg = _match_segment(lyrics_lines[gap_end_idx], transcript_segments)
                ceiling_seg = max(ceiling_seg, start_seg)
                ceiling_time = float(transcript_segments[ceiling_seg]["start"])
            else:
                ceiling_time = prev_end + sum(
                    max(len(lyrics_lines[k]) * 0.35, 3.0)
                    for k in range(gap_start_idx, gap_end_idx)
                ) + 2.0

            # Distribute gap lines proportionally between prev_end and ceiling_time
            available = ceiling_time - prev_end - 0.5  # buffer before ceiling
            total_len = sum(len(lyrics_lines[k]) for k in range(gap_start_idx, gap_end_idx))
            if total_len == 0:
                total_len = 1

            gap_prev = prev_end
            for k in range(gap_start_idx, gap_end_idx):
                lt = lyrics_lines[k]
                share = (len(lt) / total_len) * available
                line_start = gap_prev + 0.3
                line_end = line_start + share - 0.3

                results.append({
                    "text": lt,
                    "start": round(line_start, 3),
                    "end": round(line_end, 3),
                    "chars": _interpolate(lt, line_start, line_end),
                    "warning": "transcript_gap",
                })
                gap_prev = line_end

            prev_end = gap_prev

    return results


def _align_one(
    audio: np.ndarray,
    line_text: str,
    window_start: float,
    window_end: float,
    align_model,
    align_metadata: dict,
    device: str,
) -> dict:
    """Force-align a single lyrics line within the given time window."""
    segment = {
        "start": window_start,
        "end": window_end,
        "text": line_text,
    }

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
        seg_data = aligned["segments"][0] if aligned["segments"] else None

        if seg_data:
            raw_items = seg_data.get("chars", []) or seg_data.get("words", [])
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
            return {
                "text": line_text,
                "start": chars[0]["start"],
                "end": chars[-1]["end"],
                "chars": chars,
            }
        else:
            return {
                "text": line_text,
                "start": round(window_start, 3),
                "end": round(window_end, 3),
                "chars": _interpolate(line_text, window_start, window_end),
                "warning": "alignment_failed",
            }

    except Exception as e:
        return {
            "text": line_text,
            "start": round(window_start, 3),
            "end": round(window_end, 3),
            "chars": _interpolate(line_text, window_start, window_end),
            "warning": f"alignment_error: {e}",
        }


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
