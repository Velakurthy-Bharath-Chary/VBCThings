from pathlib import Path

from groq import Groq

from app.config import settings


_client = Groq(
    api_key=settings.groq_api_key,
)


SUPPORTED_AUDIO_TYPES = {
    ".wav",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".m4a",
    ".webm",
}


SILENCE_HALLUCINATIONS = {
    "thank you.",
    "thank you",
    "thank you. thank you.",
    "thank you for watching.",
    "subtitles by amara.org",
    "subtitles by",
    "thanks for watching.",
    "you",
}


def is_silence_hallucination(text: str) -> bool:
    cleaned = " ".join(text.casefold().strip().split())
    if not cleaned or cleaned in SILENCE_HALLUCINATIONS:
        return True
    if cleaned.startswith("thank you") and len(cleaned.split()) <= 4:
        return True
    return False


def transcribe_audio(
    file_path: str | Path,
    language: str | None = None,
) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError("Audio file not found.")

    if path.suffix.lower() not in SUPPORTED_AUDIO_TYPES:
        raise ValueError("Unsupported audio format.")

    with path.open("rb") as audio_file:
        response = _client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=audio_file,
            language=language,
            response_format="text",
        )

    transcription = response.strip()
    if is_silence_hallucination(transcription):
        return ""
    return transcription


# FILE PURPOSE:
# Provides speech-to-text transcription through Groq Whisper.