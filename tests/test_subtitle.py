"""Tests for ASS karaoke subtitle generation."""

import json
import pytest
from src.subtitle import generate_ass


def _make_aligned(lines):
    """Helper: build aligned dict from list of line dicts."""
    return {"lines": lines}


def _make_line(line_no, text, start, end, chars=None):
    """Helper: build a single line dict."""
    if chars is None:
        n = len(text)
        duration = (end - start) / n
        chars = [
            {"char": c, "start": start + i * duration, "end": start + (i + 1) * duration}
            for i, c in enumerate(text)
        ]
    return {"line_no": line_no, "text": text, "start": start, "end": end, "chars": chars}


def test_ass_header_present():
    """ASS output contains required header sections."""
    aligned = _make_aligned([_make_line(1, "测试", 1.0, 2.0)])
    result = generate_ass(aligned)
    assert "[Script Info]" in result
    assert "ScriptType: v4.00+" in result
    assert "[V4+ Styles]" in result
    assert "[Events]" in result


def test_kf_tags_per_char():
    """Each character gets a \\kf tag with correct centisecond duration."""
    chars = [
        {"char": "测", "start": 1.0, "end": 1.5},
        {"char": "试", "start": 1.5, "end": 2.0},
    ]
    aligned = _make_aligned([_make_line(1, "测试", 1.0, 2.0, chars)])
    result = generate_ass(aligned)

    assert "{\\kf50}测" in result
    assert "{\\kf50}试" in result


def test_time_format():
    """Dialogue timestamps are in ASS format H:MM:SS.CC."""
    chars = [
        {"char": "歌", "start": 65.0, "end": 65.5},
    ]
    aligned = _make_aligned([_make_line(1, "歌", 65.0, 65.5, chars)])
    result = generate_ass(aligned)

    assert "0:01:05.00" in result


def test_style_from_file(tmp_path):
    """ASS output uses style loaded from external preset file."""
    style_file = tmp_path / "test.ass"
    style_file.write_text("Style: TestKara,SimHei,40,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,2,10,10,30,1\n", encoding="utf-8")

    aligned = _make_aligned([_make_line(1, "歌", 1.0, 1.5)])
    result = generate_ass(aligned, style_path=str(style_file))
    assert "TestKara" in result
