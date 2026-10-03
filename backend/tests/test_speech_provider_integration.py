from pathlib import Path

import pytest

from app.ai.speech import transcribe_audio


AUDIO_FILE = Path(__file__).parents[1] / "test_audio.mp3"


@pytest.mark.integration
def test_real_groq_transcription():
    if not AUDIO_FILE.exists():
        pytest.skip(
            "Real speech integration audio not available: test_audio.mp3"
        )

    transcript = transcribe_audio(
        file_path=AUDIO_FILE,
    )

    assert transcript
    assert isinstance(transcript, str)

# FILE PURPOSE:
# Provides an optional real Groq Whisper integration test without
# requiring the audio file or API call during the normal test suite.
