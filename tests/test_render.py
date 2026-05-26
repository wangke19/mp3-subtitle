"""Tests for ffmpeg render module."""

import pytest
from src.render import build_render_commands


def test_commands_with_cover():
    """Three commands generated when cover image provided."""
    cmds = build_render_commands(
        mp3_path="song.mp3",
        ass_path="karaoke.ass",
        cover_path="cover.jpg",
        output_path="output.mp4",
        temp_dir="/tmp/test",
    )
    assert len(cmds) == 3
    assert "cover_frame.png" in " ".join(cmds[0])
    assert "boxblur" in " ".join(cmds[0])
    assert "stillimage" in " ".join(cmds[1])
    assert "song.mp3" in cmds[1]
    assert "subtitles=karaoke.ass" in " ".join(cmds[2])


def test_commands_without_cover():
    """Two commands when no cover image (gradient bg, skip cover frame step)."""
    cmds = build_render_commands(
        mp3_path="song.mp3",
        ass_path="karaoke.ass",
        cover_path=None,
        output_path="output.mp4",
        temp_dir="/tmp/test",
    )
    assert len(cmds) == 2
    assert all("boxblur" not in c for c in cmds)
    assert any("subtitles=karaoke.ass" in c for c in cmds)


def test_output_resolution():
    """Output is 1080x1080."""
    cmds = build_render_commands(
        mp3_path="song.mp3",
        ass_path="karaoke.ass",
        cover_path="cover.jpg",
        output_path="output.mp4",
        temp_dir="/tmp/test",
    )
    cover_cmd = cmds[0]
    assert "1080:1080" in " ".join(cover_cmd)
