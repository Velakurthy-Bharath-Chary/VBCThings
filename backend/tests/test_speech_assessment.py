import json
from unittest.mock import patch

from app.ai.speech_assessment import assess_answer


def _assessment_json(quote="A function accepts input and returns a value."):
    return json.dumps({
        "classification": "Partially Correct",
        "evidence_quotes": [quote],
        "covered_concepts": ["functions accept input"],
        "missing_concepts": ["functions can transform input"],
        "possible_misconceptions": [],
        "reasoning": "The transcript states two ideas in the reference but omits one key point.",
    })


def test_speech_assessment_returns_reference_based_feedback():
    with patch("app.ai.speech_assessment.generate_answer", return_value=_assessment_json()):
        result = assess_answer(
            "A function accepts input and returns a value.",
            "A function accepts input, transforms it, and returns a value.",
        )

    assert result["classification"] == "Partially Correct"
    assert result["evidence_quotes"] == ["A function accepts input and returns a value."]
    assert result["missing_concepts"] == ["functions can transform input"]
    assert result["input_truncated"] is False


def test_speech_assessment_rejects_quotes_not_present_in_transcript():
    with patch("app.ai.speech_assessment.generate_answer", return_value=_assessment_json("invented evidence")):
        assert assess_answer("A function returns a value.", "A function returns a result.") is None


def test_speech_assessment_fails_safely_when_provider_is_unavailable():
    with patch("app.ai.speech_assessment.generate_answer", side_effect=RuntimeError("private provider details")):
        assert assess_answer("A function returns a value.", "A function returns a result.") is None


# FILE PURPOSE:
# Verifies structured spoken-answer feedback, exact quote grounding,
# and fail-safe behavior when the configured LLM cannot assess an answer.
