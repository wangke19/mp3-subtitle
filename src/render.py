"""ffmpeg rendering: cover image + blur background + subtitle burn → MP4."""

import subprocess
import shutil
from pathlib import Path


def build_render_commands(
    mp3_path: str,
    ass_path: str,
    output_path: str,
    temp_dir: str,
    cover_path: str | None = None,
) -> list[list[str]]:
    """Build the list of ffmpeg commands to render the final video.

    Returns a list of commands, each as a list of strings suitable for subprocess.run.
    """
    temp = Path(temp_dir)
    temp.mkdir(parents=True, exist_ok=True)

    cover_frame = str(temp / "cover_frame.png")
    base_video = str(temp / "base_video.mp4")
    cmds = []

    if cover_path:
        cmds.append([
            "ffmpeg", "-y", "-i", cover_path, "-filter_complex",
            (
                "[0:v]scale=1080:1080:force_original_aspect_ratio=decrease[fg];"
                "[0:v]scale=1080:1080:force_original_aspect_ratio=increase,boxblur=20[bg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2"
            ),
            "-frames:v", "1", cover_frame,
        ])
        bg_input = ["-loop", "1", "-i", cover_frame]
    else:
        bg_input = [
            "-f", "lavfi", "-i",
            "color=c=black:s=1080x1080:d=999,"
            "gradient=color1=0x1a1a2e:color2=0x16213e",
        ]
        base_video = str(temp / "base_video.mp4")
        cover_frame = None

    cmds.append([
        "ffmpeg", "-y",
        *bg_input,
        "-i", mp3_path,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest", base_video,
    ])

    escaped_ass = ass_path.replace("\\", "\\\\\\\\").replace(":", "\\\\:")
    cmds.append([
        "ffmpeg", "-y", "-i", base_video,
        "-vf", f"subtitles={escaped_ass}",
        "-c:a", "copy", output_path,
    ])

    return cmds


def render(
    mp3_path: str,
    ass_path: str,
    output_path: str,
    cover_path: str | None = None,
    temp_dir: str | None = None,
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
    parser.add_argument("--output", default="output.mp4")
    parser.add_argument("--temp-dir", default=None)
    args = parser.parse_args()

    out = render(args.mp3_path, args.ass_path, args.output, args.cover, args.temp_dir)
    print(f"Video saved to {out}")


if __name__ == "__main__":
    main()
