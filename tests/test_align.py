"""Tests for lyrics alignment module."""

import json
import pytest
from src.align import align_lyrics


def _make_transcript(chars_with_times):
    """Helper: build a transcript dict from [(char, start, end), ...] list."""
    flat_chars = [
        {"char": c, "start": s, "end": e} for c, s, e in chars_with_times
    ]
    text = "".join(c for c, _, _ in chars_with_times)
    return {
        "segments": [
            {
                "start": chars_with_times[0][1],
                "end": chars_with_times[-1][2],
                "text": text,
                "chars": flat_chars,
            }
        ]
    }


def test_single_line_exact_match(tmp_path):
    """Lyrics line matches transcript exactly."""
    transcript = _make_transcript([
        ("今", 1.0, 1.3), ("天", 1.3, 1.6), ("天", 1.6, 1.9),
        ("气", 1.9, 2.2), ("真", 2.2, 2.5), ("好", 2.5, 2.8),
    ])
    lyrics = tmp_path / "lyrics.txt"
    lyrics.write_text("今天天气真好\n", encoding="utf-8")

    result = align_lyrics(transcript, str(lyrics))
    assert len(result["lines"]) == 1
    line = result["lines"][0]
    assert line["text"] == "今天天气真好"
    assert line["start"] == 1.0
    assert line["end"] == 2.8
    assert len(line["chars"]) == 6
    assert line["chars"][0] == {"char": "今", "start": 1.0, "end": 1.3}


def test_two_lines(tmp_path):
    """Two lyrics lines map to two time spans."""
    transcript = _make_transcript([
        ("今", 1.0, 1.3), ("天", 1.3, 1.6), ("天", 1.6, 1.9),
        ("气", 1.9, 2.2), ("真", 2.2, 2.5), ("好", 2.5, 2.8),
        ("明", 3.0, 3.3), ("天", 3.3, 3.6), ("见", 3.6, 3.9),
    ])
    lyrics = tmp_path / "lyrics.txt"
    lyrics.write_text("今天天气真好\n明天见\n", encoding="utf-8")

    result = align_lyrics(transcript, str(lyrics))
    assert len(result["lines"]) == 2
    assert result["lines"][0]["text"] == "今天天气真好"
    assert result["lines"][0]["start"] == 1.0
    assert result["lines"][1]["text"] == "明天见"
    assert result["lines"][1]["start"] == 3.0


def test_filler_words_skipped(tmp_path):
    """Filler words in transcript are skipped when matching lyrics."""
    transcript = _make_transcript([
        ("啊", 0.5, 0.8), ("今", 1.0, 1.3), ("天", 1.3, 1.6),
    ])
    lyrics = tmp_path / "lyrics.txt"
    lyrics.write_text("今天\n", encoding="utf-8")

    result = align_lyrics(transcript, str(lyrics))
    assert len(result["lines"]) == 1
    assert result["lines"][0]["text"] == "今天"
    assert result["lines"][0]["start"] == 1.0
    assert result["lines"][0]["end"] == 1.6


def test_unmatched_line_gets_interpolated_time(tmp_path):
    """Lyrics line not found in transcript gets interpolated timing."""
    transcript = _make_transcript([
        ("今", 1.0, 1.3), ("天", 1.3, 1.6),
    ])
    lyrics = tmp_path / "lyrics.txt"
    lyrics.write_text("今天\n看不见的歌词\n", encoding="utf-8")

    result = align_lyrics(transcript, str(lyrics))
    assert len(result["lines"]) == 2
    assert result["lines"][0]["text"] == "今天"
    assert result["lines"][1]["start"] >= result["lines"][0]["end"]
