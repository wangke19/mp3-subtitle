"""WhisperX transcription with forced alignment for Chinese audio."""

import json
from pathlib import Path

import whisperx


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

    model = whisperx.load_model(
        model_name,
        device,
        compute_type=compute_type,
        language=language,
        asr_options={"word_timestamps": True, "condition_on_previous_text": True},
    )
    transcribe_kwargs = dict(audio, batch_size=batch_size, language=language)
    if initial_prompt:
        transcribe_kwargs["initial_prompt"] = initial_prompt
    result = model.transcribe(**transcribe_kwargs)
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
