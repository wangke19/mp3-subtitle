"""ffmpeg rendering: cover image + blur background + subtitle burn → MP4."""

import subprocess
import shutil
from pathlib import Path


def _image_filter_chain(input_label: str, idx: int) -> tuple[str, str]:
    """Build ffmpeg filter chain for scale+blur+overlay on one image.

    Returns (filter_string, output_label).
    """
    return (
        f"[{input_label}]scale=1080:1080:force_original_aspect_ratio=increase,boxblur=20[bg{idx}];"
        f"[{input_label}]scale=1080:1080:force_original_aspect_ratio=decrease[fg{idx}];"
        f"[bg{idx}][fg{idx}]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v{idx}]"
    ), f"v{idx}"


def build_render_commands(
    mp3_path: str,
    ass_path: str,
    output_path: str,
    temp_dir: str,
    cover_path: str | None = None,
    bg_images: list[str] | None = None,
) -> list[list[str]]:
    """Build the list of ffmpeg commands to render the final video.

    Background modes (in priority order):
    1. bg_images with .gif → animated GIF background
    2. bg_images with 2+ files → crossfade slideshow
    3. bg_images with 1 non-gif → same as static cover
    4. cover_path → static cover (existing behavior)
    5. None → solid color background
    """
    temp = Path(temp_dir)
    temp.mkdir(parents=True, exist_ok=True)

    cover_frame = str(temp / "cover_frame.png")
    bg_video = str(temp / "bg_processed.mp4")
    base_video = str(temp / "base_video.mp4")
    cmds = []

    # --- Determine background mode ---
    is_gif = (
        bg_images
        and len(bg_images) == 1
        and bg_images[0].lower().endswith(".gif")
    )
    is_slideshow = bg_images and len(bg_images) >= 2

    if is_gif:
        # GIF mode: process frames into video, then loop
        filt, _ = _image_filter_chain("0:v", 0)
        cmds.append([
            "ffmpeg", "-y",
            "-i", bg_images[0],
            "-filter_complex", filt,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-an", bg_video,
        ])
        cmds.append([
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", bg_video,
            "-i", mp3_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest", base_video,
        ])

    elif is_slideshow:
        # Slideshow mode: process each image, crossfade them into a video
        n = len(bg_images)
        fade_dur = 0.5

        # Get audio duration to calculate per-image display time
        dur_per_img = _get_audio_duration(mp3_path)
        if dur_per_img > 0:
            dur_per_img = dur_per_img / n + fade_dur
        else:
            dur_per_img = 10.0

        # Build input args and filter chains
        inputs = []
        filters = []
        for idx, img in enumerate(bg_images):
            inputs.extend(["-loop", "1", "-t", f"{dur_per_img:.1f}", "-i", img])
            filt, _ = _image_filter_chain(f"{idx}:v", idx)
            filters.append(filt)

        # Build xfade chain
        if n == 2:
            offset = dur_per_img - fade_dur
            filters.append(f"[v0][v1]xfade=transition=fade:duration={fade_dur}:offset={offset:.1f}[out]")
        else:
            offset = dur_per_img - fade_dur
            filters.append(f"[v0][v1]xfade=transition=fade:duration={fade_dur}:offset={offset:.1f}[x0]")
            for idx in range(2, n):
                offset += dur_per_img - fade_dur
                prev = f"x{idx - 2}" if idx > 2 else "x0"
                out_label = "out" if idx == n - 1 else f"x{idx - 1}"
                filters.append(
                    f"[{prev}][v{idx}]xfade=transition=fade:duration={fade_dur}:offset={offset:.1f}[{out_label}]"
                )

        cmds.append([
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[out]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-an", bg_video,
        ])

        cmds.append([
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", bg_video,
            "-i", mp3_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest", base_video,
        ])

    elif cover_path:
        # Static cover mode (existing behavior)
        cmds.append([
            "ffmpeg", "-y", "-i", cover_path, "-filter_complex",
            (
                "[0:v]scale=1080:1080:force_original_aspect_ratio=decrease[fg];"
                "[0:v]scale=1080:1080:force_original_aspect_ratio=increase,boxblur=20[bg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2"
            ),
            "-frames:v", "1", cover_frame,
        ])
        cmds.append([
            "ffmpeg", "-y",
            "-loop", "1", "-i", cover_frame,
            "-i", mp3_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest", base_video,
        ])

    else:
        # Solid color background
        cmds.append([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=1080x1080:d=999",
            "-i", mp3_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest", base_video,
        ])

    # Subtitle burn step (always last)
    escaped_ass = ass_path.replace("\\", "\\\\\\\\").replace(":", "\\\\:")
    cmds.append([
        "ffmpeg", "-y", "-i", base_video,
        "-vf", f"subtitles={escaped_ass}",
        "-c:a", "copy", output_path,
    ])

    return cmds


def _get_audio_duration(mp3_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", mp3_path],
            capture_output=True, text=True,
        )
        return float(result.stdout.strip())
    except (ValueError, FileNotFoundError):
        return 0.0


def render(
    mp3_path: str,
    ass_path: str,
    output_path: str,
    cover_path: str | None = None,
    temp_dir: str | None = None,
    bg_images: list[str] | None = None,
) -> str:
    """Execute the full rendering pipeline.

    Returns the path to the output MP4 file.
    """
    if temp_dir is None:
        temp_dir = str(Path(output_path).parent / "temp")

    cmds = build_render_commands(
        mp3_path=mp3_path,
        ass_path=ass_path,
        output_path=output_path,
        temp_dir=temp_dir,
        cover_path=cover_path,
        bg_images=bg_images,
    )

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH. Install ffmpeg first.")

    for i, cmd in enumerate(cmds, 1):
        print(f"[render] Step {i}/{len(cmds)}: {' '.join(cmd[:6])}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg step {i} failed (exit {result.returncode}):\n"
                f"STDERR: {result.stderr[-500:]}"
            )

    return output_path


def main():
    """CLI: render <mp3> <ass> [--cover cover.jpg] [--output output.mp4]"""
    import argparse

    parser = argparse.ArgumentParser(description="Render MP4 with subtitles")
    parser.add_argument("mp3_path", help="Path to MP3 file")
    parser.add_argument("ass_path", help="Path to ASS subtitle file")
    parser.add_argument("--cover", default=None, help="Path to cover image")
    parser.add_argument("--bg-images", nargs="+", default=None,
                        help="Background: GIF file or multiple images for slideshow")
    parser.add_argument("--output", default="output.mp4")
    parser.add_argument("--temp-dir", default=None)
    args = parser.parse_args()

    out = render(
        args.mp3_path, args.ass_path, args.output,
        cover_path=args.cover, temp_dir=args.temp_dir,
        bg_images=args.bg_images,
    )
    print(f"Video saved to {out}")


if __name__ == "__main__":
    main()
