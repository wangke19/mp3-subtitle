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
    """Two commands when no cover image (solid color bg)."""
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


def test_gif_mode():
    """GIF background produces process + loop-merge + subtitle burn commands."""
    cmds = build_render_commands(
        mp3_path="song.mp3",
        ass_path="karaoke.ass",
        output_path="output.mp4",
        temp_dir="/tmp/test",
        bg_images=["anim.gif"],
    )
    # Step 1: process GIF → bg_video, Step 2: merge with audio, Step 3: subtitles
    assert len(cmds) == 3
    gif_cmd = " ".join(cmds[0])
    assert "anim.gif" in gif_cmd
    assert "boxblur" in gif_cmd
    merge_cmd = " ".join(cmds[1])
    assert "-stream_loop" in merge_cmd
    assert "song.mp3" in merge_cmd


def test_slideshow_mode():
    """Multiple images produce xfade slideshow + loop-merge + subtitle burn."""
    cmds = build_render_commands(
        mp3_path="song.mp3",
        ass_path="karaoke.ass",
        output_path="output.mp4",
        temp_dir="/tmp/test",
        bg_images=["img1.jpg", "img2.jpg", "img3.jpg"],
    )
    assert len(cmds) == 3
    slide_cmd = " ".join(cmds[0])
    assert "img1.jpg" in slide_cmd
    assert "img2.jpg" in slide_cmd
    assert "img3.jpg" in slide_cmd
    assert "xfade" in slide_cmd
    assert "boxblur" in slide_cmd
    merge_cmd = " ".join(cmds[1])
    assert "-stream_loop" in merge_cmd
