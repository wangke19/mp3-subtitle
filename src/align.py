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


def _is_marker_line(text: str, line_no: int, all_lines: list[str]) -> bool:
    """Check if a lyrics line is a marker (intro, interlude, title) not meant for matching."""
    stripped = text.strip()
    # Bracketed markers like [前奏], [间奏]
    if stripped.startswith("[") and stripped.endswith("]"):
        return True
    return False


def _find_match_span(lyrics_line: str, char_seq: list[dict], search_start: int) -> tuple[int, int] | None:
    """Find best matching subsequence for lyrics_line in char_seq after search_start.

    Searches progressively forward so lines stay in chronological order.
    Uses a large window to skip intro/watermark segments.
    Extends match backwards to include unmatched prefix characters.
    """
    if not lyrics_line or not char_seq:
        return None

    seq_text = "".join(c["char"] for c in char_seq)

    # Search from search_start to end of transcript
    remaining_text = seq_text[search_start:]
    if not remaining_text:
        return None

    min_match = max(len(lyrics_line) * 0.4, 2)

    sm = SequenceMatcher(None, lyrics_line, remaining_text)
    matches = sm.get_matching_blocks()

    # Pick the first good match (closest to search_start)
    for match in sorted(matches, key=lambda m: m.b):
        if match.size >= min_match:
            start_idx = search_start + match.b
            end_idx = start_idx + match.size
            matched_chars = char_seq[start_idx:end_idx]
            if matched_chars:
                # Try to extend backwards to capture unmatched prefix
                start_idx = _extend_match_backwards(lyrics_line, char_seq, start_idx)
                return (start_idx, end_idx)

    return None


def _extend_match_backwards(lyrics_line: str, char_seq: list[dict], match_start: int) -> int:
    """Try to extend match start backwards to include more of the lyrics line.

    If the matched text only covers the latter part of the lyrics line,
    check if characters before match_start correspond to the lyrics prefix.
    Skips spaces in lyrics during matching.
    """
    # Find what the match covers in the lyrics
    matched_text_from = "".join(c["char"] for c in char_seq[match_start:match_start + len(lyrics_line)])
    sm = SequenceMatcher(None, lyrics_line, matched_text_from)
    opcodes = sm.get_opcodes()

    # Find the first 'equal' opcode — what part of lyrics is matched
    first_equal_i1 = len(lyrics_line)
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal" and i1 < first_equal_i1:
            first_equal_i1 = i1
            break

    if first_equal_i1 == 0:
        return match_start

    # Build the unmatched prefix, skipping spaces for comparison
    lyrics_prefix_nospace = lyrics_line[:first_equal_i1].replace(" ", "")

    # Walk backwards through char_seq matching prefix chars
    best_start = match_start
    prefix_idx = len(lyrics_prefix_nospace) - 1  # start from end of prefix
    for back in range(1, min(match_start, len(lyrics_prefix_nospace) * 2) + 1):
        idx = match_start - back
        if idx < 0 or prefix_idx < 0:
            break
        if char_seq[idx]["char"] == lyrics_prefix_nospace[prefix_idx]:
            best_start = idx
            prefix_idx -= 1
        elif char_seq[idx]["char"] == " ":
            best_start = idx  # skip spaces in transcript
        else:
            break

    return best_start


def _build_line_chars(line_text: str, matched_chars: list[dict]) -> list[dict]:
    """Build char timing list for a lyrics line from matched transcript chars."""
    if len(matched_chars) == len(line_text):
        return [
            {"char": c["char"], "start": c["start"], "end": c["end"]}
            for c in matched_chars
        ]

    # When matched chars cover only part of the line, interpolate missing parts.
    # Split into: prefix (before match) + matched portion + suffix (after match).
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
            # Lyrics chars not in transcript — interpolate timing
            n_insert = i2 - i1
            if line_chars:
                # After some matched chars — extend from previous end
                prev_end = line_chars[-1]["end"]
                next_start = matched_chars[j1]["start"] if j1 < len(matched_chars) else prev_end + n_insert * 0.3
                if next_start <= prev_end:
                    next_start = prev_end + n_insert * 0.3
                duration = (next_start - prev_end) / n_insert
            elif matched_chars:
                # Before any matched chars — prepend before first match
                first_start = matched_chars[0]["start"]
                duration = 0.3  # 0.3s per char for prefix
                for k in range(n_insert):
                    line_chars.append({
                        "char": line_text[i1 + k],
                        "start": round(first_start - (n_insert - k) * duration, 3),
                        "end": round(first_start - (n_insert - k - 1) * duration, 3),
                    })
                continue
            else:
                duration = 0.3
            for k in range(n_insert):
                line_chars.append({
                    "char": line_text[i1 + k],
                    "start": round(prev_end + k * duration, 3),
                    "end": round(prev_end + (k + 1) * duration, 3),
                })
        elif tag == "delete":
            # Lyrics chars not in matched transcript — interpolate timing
            n_delete = i2 - i1
            if matched_chars:
                if j1 == 0 and not line_chars:
                    # Prefix: before first matched char — prepend backwards
                    first_start = matched_chars[0]["start"]
                    duration = min(0.3, first_start / max(n_delete, 1))
                    for k in range(n_delete):
                        line_chars.append({
                            "char": line_text[i1 + k],
                            "start": round(first_start - (n_delete - k) * duration, 3),
                            "end": round(first_start - (n_delete - k - 1) * duration, 3),
                        })
                elif j1 < len(matched_chars):
                    # Middle: between matched chars — split gap evenly
                    prev_end = line_chars[-1]["end"] if line_chars else matched_chars[max(j1-1, 0)]["end"]
                    next_start = matched_chars[j1]["start"]
                    if next_start <= prev_end:
                        next_start = prev_end + n_delete * 0.3
                    duration = (next_start - prev_end) / n_delete
                    for k in range(n_delete):
                        line_chars.append({
                            "char": line_text[i1 + k],
                            "start": round(prev_end + k * duration, 3),
                            "end": round(prev_end + (k + 1) * duration, 3),
                        })
                else:
                    # Suffix: after last matched char — extend
                    prev_end = line_chars[-1]["end"] if line_chars else 0
                    duration = 0.3
                    for k in range(n_delete):
                        line_chars.append({
                            "char": line_text[i1 + k],
                            "start": round(prev_end + k * duration, 3),
                            "end": round(prev_end + (k + 1) * duration, 3),
                        })

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


def _parse_lyrics_with_header(lyrics_path: str) -> tuple[list[str], list[str]]:
    """Parse lyrics file, separating header (title + markers) from body.

    Returns (header_lines, body_lines). Header lines are everything before
    the first real lyrics line (or until we see a bracket marker).
    """
    text = Path(lyrics_path).read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    non_empty = [l for l in lines if l]

    if not non_empty:
        return ([], [])

    # If the first non-empty line is followed by bracket markers or empty lines,
    # treat it as a header block
    header_end = 0
    for i, line in enumerate(non_empty):
        if line.startswith("[") and line.endswith("]"):
            header_end = i + 1  # include this marker line in header
        elif header_end > 0:
            break  # we've passed the header markers

    # If we found bracket markers, everything before+including them is header
    if header_end > 0:
        return (non_empty[:header_end], non_empty[header_end:])

    # No bracket markers found - no header separation
    return ([], non_empty)


def align_lyrics(transcript: dict, lyrics_path: str) -> dict:
    """Align transcript character timestamps to lyrics lines."""
    header_lines, body_lines = _parse_lyrics_with_header(lyrics_path)
    char_seq = _flatten_chars(transcript)

    result_lines = []
    search_start = 0

    # Add header lines as markers
    for i, line_text in enumerate(header_lines):
        result_lines.append({
            "line_no": i + 1,
            "text": line_text,
            "start": 0.0,
            "end": 0.0,
            "chars": [],
            "marker": True,
        })

    # Match body lines progressively
    line_no_offset = len(header_lines)
    for i, line_text in enumerate(body_lines):
        line_no = line_no_offset + i + 1

        if _is_marker_line(line_text, line_no, body_lines):
            result_lines.append({
                "line_no": line_no,
                "text": line_text,
                "start": 0.0,
                "end": 0.0,
                "chars": [],
                "marker": True,
            })
            continue

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
            for prev in reversed(result_lines):
                if "marker" not in prev and prev.get("end", 0) > 0:
                    start_time = prev["end"] + 0.1
                    break
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

    # Assign timing to marker lines
    first_match_start = None
    for line in result_lines:
        if "marker" not in line and line.get("start", 0) > 0:
            first_match_start = line["start"]
            break

    for line in result_lines:
        if "marker" in line:
            if first_match_start and first_match_start > 0:
                line["start"] = round(max(first_match_start - 5.0, 0.0), 3)
                line["end"] = round(first_match_start - 0.1, 3)
                line["chars"] = _interpolate_chars(line["text"], line["start"], line["end"])
            del line["marker"]

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
