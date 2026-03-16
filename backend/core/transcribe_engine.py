import whisper
import anthropic
import json
from pathlib import Path


def _format_timestamp(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format HH:MM:SS,mmm."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def _build_srt(segments: list) -> str:
    """Build SRT subtitle string from Whisper segments."""
    lines = []
    for i, seg in enumerate(segments, start=1):
        start = _format_timestamp(seg["start"])
        end = _format_timestamp(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def _build_chapters(segments: list, interval: int = 60) -> list:
    """Group segments into chapters at ~interval-second boundaries."""
    if not segments:
        return []

    chapters = []
    current_start = 0.0
    current_label_words = []

    for seg in segments:
        if seg["start"] - current_start >= interval and current_label_words:
            mins = int(current_start // 60)
            secs = int(current_start % 60)
            time_str = f"{mins}:{secs:02d}"
            label = " ".join(current_label_words[:8]).strip()
            chapters.append({"time": time_str, "label": label})
            current_start = seg["start"]
            current_label_words = []

        current_label_words.extend(seg["text"].strip().split())

    # Final chapter
    if current_label_words:
        mins = int(current_start // 60)
        secs = int(current_start % 60)
        time_str = f"{mins}:{secs:02d}"
        label = " ".join(current_label_words[:8]).strip()
        chapters.append({"time": time_str, "label": label})

    return chapters


def _get_ai_analysis(transcript: str, api_key: str) -> dict:
    """Call Claude API for summary and key topics."""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system="You are an audio transcription assistant.",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Given this transcript, provide:\n"
                        "1. A concise 3-5 sentence summary\n"
                        "2. 5 key topics as a JSON array\n"
                        "Return JSON only: {\"summary\": \"string\", \"topics\": [\"string\"]}\n\n"
                        f"Transcript:\n{transcript[:12000]}"
                    ),
                }
            ],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0]
        data = json.loads(raw)
        return {
            "summary": data.get("summary", ""),
            "topics": data.get("topics", []),
        }
    except Exception:
        return {"summary": "", "topics": []}


def transcribe_audio(file_path: Path, anthropic_key: str = "") -> dict:
    """Transcribe an audio file using Whisper and optionally analyze with Claude.

    Returns dict with: transcript, summary, topics, chapters, srt
    """
    model = whisper.load_model("small")
    result = model.transcribe(str(file_path))

    transcript = result["text"].strip()
    segments = result.get("segments", [])
    srt = _build_srt(segments)
    chapters = _build_chapters(segments)

    if anthropic_key:
        analysis = _get_ai_analysis(transcript, anthropic_key)
    else:
        analysis = {"summary": "", "topics": []}

    return {
        "transcript": transcript,
        "summary": analysis["summary"],
        "topics": analysis["topics"],
        "chapters": chapters,
        "srt": srt,
    }
