"""Generate ASS karaoke subtitle file with \\kf smooth highlighting."""

from pathlib import Path

_SCRIPT_INFO = """[Script Info]
Title: MP3 Karaoke Subtitle
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

"""

_EVENTS_HEADER = "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"


def _seconds_to_ass(seconds: float) -> str:
    """Convert seconds to ASS timestamp format H:MM:SS.CC."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _build_dialogue_line(line: dict, style_name: str) -> str:
    """Build a single ASS Dialogue line with \\kf tags per character."""
    chars = line.get("chars", [])
    if not chars:
        return ""

    start_ass = _seconds_to_ass(line["start"])
    end_ass = _seconds_to_ass(line["end"])

    text_parts = []
    for c in chars:
        duration_cs = round((c["end"] - c["start"]) * 100)
        if duration_cs < 1:
            duration_cs = 1
        text_parts.append("{\\kf" + str(duration_cs) + "}" + c["char"])

    text = "{\\2c&H0000D7FF&}" + "".join(text_parts)
    return f"Dialogue: 0,{start_ass},{end_ass},{style_name},,0,0,0,,{text}"


def generate_ass(aligned: dict, style_path: str = None, offset: float = 0.0) -> str:
    """Generate complete ASS file content from aligned lyrics data.

    Args:
        aligned: Dict with 'lines' key from align.py
        style_path: Path to ASS style preset file.
        offset: Seconds to shift all subtitles forward (positive = later).
    """
    if style_path is None:
        style_path = str(Path(__file__).parent.parent / "styles" / "default.ass")

    style_line = Path(style_path).read_text(encoding="utf-8").strip()
    style_name = style_line.split(",")[0].replace("Style: ", "").strip()

    parts = [
        _SCRIPT_INFO,
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n",
        style_line + "\n\n",
        _EVENTS_HEADER,
    ]

    for line in aligned.get("lines", []):
        shifted = {
            **line,
            "start": line["start"] + offset,
            "end": line["end"] + offset,
            "chars": [
                {**c, "start": c["start"] + offset, "end": c["end"] + offset}
                for c in line.get("chars", [])
            ],
        }
        dialogue = _build_dialogue_line(shifted, style_name)
        if dialogue:
            parts.append(dialogue + "\n")

    return "".join(parts)


def main():
    """CLI: subtitle <aligned.json> [--style styles/default.ass] [--output karaoke.ass]"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Generate ASS karaoke subtitles")
    parser.add_argument("aligned", help="Path to aligned.json")
    parser.add_argument("--style", default=None, help="Path to ASS style preset")
    parser.add_argument("--output", default="karaoke.ass")
    args = parser.parse_args()

    aligned = json.loads(Path(args.aligned).read_text(encoding="utf-8"))
    content = generate_ass(aligned, style_path=args.style)
    Path(args.output).write_text(content, encoding="utf-8")
    print(f"ASS subtitle saved to {args.output}")


if __name__ == "__main__":
    main()
