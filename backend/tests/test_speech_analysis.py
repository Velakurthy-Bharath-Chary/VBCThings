from app.ai.speech_analysis import analyze_semantics


transcript = """
I am studying computer science and I enjoy building software applications.
I want to improve my understanding of artificial intelligence and machine learning.
My goal is to become a strong software engineer.
"""

def test_empty_or_silence_transcript_returns_no_speech_detected():
    res = analyze_semantics("")
    assert res.get("no_speech_detected") is True
    assert res["language_signals"]["word_count"] == 0

    res2 = analyze_semantics("   ")
    assert res2.get("no_speech_detected") is True


# FILE PURPOSE:
# Tests speech transcript analysis independently from the API layer.