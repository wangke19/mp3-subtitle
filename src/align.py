"""Map WhisperX character timestamps onto user-provided lyrics lines."""

import json
from difflib import SequenceMatcher
from pathlib import Path


def _flatten_chars(transcript: dict) -> list[dict]:
    """Flatten all segments' chars into a single sequence."""
    chars = []
    for seg in transcript["segments"]:
        chars.extend(seg.get("chars", []))
    return chars


def _parse_lyrics(lyrics_path: str) -> list[str]:
    """Read lyrics file, return list of non-empty lines."""
    text = Path(lyrics_path).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _find_match_span(lyrics_line: str, char_seq: list[dict], search_start: int) -> tuple[int, int] | None:
    """Find best matching subsequence for lyrics_line in char_seq starting at search_start.

    Searches the full transcript text (not just a small window) and picks the
    best match closest to search_start. This handles intro/watermark segments
    that don't appear in the lyrics.
    """
    if not lyrics_line or not char_seq:
        return None

    seq_text = "".join(c["char"] for c in char_seq)
    min_match = max(len(lyrics_line) * 0.4, 2)

    best_match = None
    best_score = 0

    sm = SequenceMatcher(None, lyrics_line, seq_text)
    for match in sm.get_matching_blocks():
        if match.size >= min_match and match.size > best_score:
            best_score = match.size
            best_match = match

    if not best_match:
        return None

    start_idx = best_match.b
    end_idx = start_idx + best_match.size

    matched_chars = char_seq[start_idx:end_idx]
    if not matched_chars:
        return None

    return (start_idx, end_idx)


def _build_line_chars(line_text: str, matched_chars: list[dict]) -> list[dict]:
    """Build char timing list for a lyrics line from matched transcript chars."""
    if len(matched_chars) == len(line_text):
        return [
            {"char": c["char"], "start": c["start"], "end": c["end"]}
            for c in matched_chars
        ]

    matched_text = "".join(c["char"] for c in matched_chars)
    sm = SequenceMatcher(None, line_text, matched_text)

    line_chars = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                mc = matched_chars[j1 + k]
                line_chars.append({
                    "char": line_text[i1 + k],
                    "start": mc["start"],
                    "end": mc["end"],
                })
        elif tag == "replace":
            for k in range(i2 - i1):
                mc_idx = j1 + min(k, j2 - j1 - 1)
                mc = matched_chars[mc_idx]
                line_chars.append({
                    "char": line_text[i1 + k],
                    "start": mc["start"],
                    "end": mc["end"],
                })
        elif tag == "insert":
            prev_end = line_chars[-1]["end"] if line_chars else matched_chars[0]["start"]
            next_start = matched_chars[j1]["start"] if j1 < len(matched_chars) else prev_end + 0.3
            duration = (next_start - prev_end) / max(i2 - i1, 1)
            for k in range(i2 - i1):
                line_chars.append({
                    "char": line_text[i1 + k],
                    "start": round(prev_end + k * duration, 3),
                    "end": round(prev_end + (k + 1) * duration, 3),
                })
        elif tag == "delete":
            pass

    return line_chars


def _interpolate_chars(text: str, start: float, end: float) -> list[dict]:
    """Evenly distribute char timings across the given span."""
    if not text:
        return []
    n = len(text)
    duration = (end - start) / n
    return [
        {
            "char": c,
            "start": round(start + i * duration, 3),
            "end": round(start + (i + 1) * duration, 3),
        }
        for i, c in enumerate(text)
    ]


def align_lyrics(transcript: dict, lyrics_path: str) -> dict:
    """Align transcript character timestamps to lyrics lines."""
    lyrics_lines = _parse_lyrics(lyrics_path)
    char_seq = _flatten_chars(transcript)

    result_lines = []
    search_start = 0

    for line_no, line_text in enumerate(lyrics_lines, 1):
        span = _find_match_span(line_text, char_seq, search_start)

        if span:
            start_idx, end_idx = span
            matched_chars = char_seq[start_idx:end_idx]
            line_chars = _build_line_chars(line_text, matched_chars)

            result_lines.append({
                "line_no": line_no,
                "text": line_text,
                "start": matched_chars[0]["start"],
                "end": matched_chars[-1]["end"],
                "chars": line_chars,
            })
            search_start = end_idx
        else:
            start_time = 0.0
            end_time = 0.0
            if result_lines:
                start_time = result_lines[-1]["end"] + 0.1
            elif char_seq:
                start_time = char_seq[0]["start"]

            if start_time > 0:
                end_time = start_time + max(len(line_text) * 0.3, 2.0)

            result_lines.append({
                "line_no": line_no,
                "text": line_text,
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "chars": _interpolate_chars(line_text, start_time, end_time),
                "warning": "unmatched",
            })

    return {"lines": result_lines}


def main():
    """CLI: align <transcript.json> <lyrics.txt> [--output aligned.json]"""
    import argparse

    parser = argparse.ArgumentParser(description="Align lyrics to transcript")
    parser.add_argument("transcript", help="Path to transcript.json")
    parser.add_argument("lyrics", help="Path to lyrics.txt")
    parser.add_argument("--output", default="aligned.json")
    args = parser.parse_args()

    transcript = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
    result = align_lyrics(transcript, args.lyrics)
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Aligned lyrics saved to {args.output}")


if __name__ == "__main__":
    main()
