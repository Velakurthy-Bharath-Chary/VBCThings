from unittest.mock import Mock

from app.ai import speech_analysis


def test_reference_comparison_reports_similarity_without_grading(monkeypatch):
    model = Mock()
    model.encode.return_value = [[0.1, 0.2], [0.1, 0.2]]
    monkeypatch.setattr(speech_analysis, "_embedding_model", model)
    monkeypatch.setattr(speech_analysis, "assess_answer", lambda *_args: None)
    similarity = Mock()
    similarity.item.return_value = 0.84
    monkeypatch.setattr(speech_analysis.util, "cos_sim", lambda *_args: similarity)

    result = speech_analysis.analyze_semantics(
        "A function returns a value.",
        "A function gives back a result.",
    )

    assert result["answer_relevance"]["similarity"] == 0.84
    assert "semantically close" in result["answer_relevance"]["interpretation"]
    assert "not a correctness grade" in result["answer_relevance"]["basis"]
    assert result["personalized_feedback"]["strengths"]
    assert result["personalized_feedback"]["next_steps"]
    assert any("reference" in item.lower() for item in result["personalized_feedback"]["strengths"])


def test_personalized_feedback_changes_with_transcript_signals():
    short_result = speech_analysis.analyze_semantics("A function returns a value.")
    longer_result = speech_analysis.analyze_semantics(
        "A function accepts input. It processes that input and returns a useful result."
    )

    assert any("Expand" in item for item in short_result["personalized_feedback"]["next_steps"])
    assert short_result["personalized_feedback"] != longer_result["personalized_feedback"]


def test_cefr_estimate_requires_minimum_sample_and_stays_within_a2_to_c1():
    short = speech_analysis.analyze_semantics("A function returns a value.")
    assert short["cefr_estimate"] == {
        "level": None,
        "sample_sufficient": False,
        "basis": "At least 30 transcript words are needed for this rough estimate; this is not a certified CEFR assessment.",
    }

    long_transcript = "A function can accept several inputs and transform them into a useful result. " * 3
    estimate = speech_analysis.analyze_semantics(long_transcript)["cefr_estimate"]
    assert estimate["level"] in {"A2", "B1", "B2", "C1"}
    assert estimate["sample_sufficient"] is True


# FILE PURPOSE:
# Verifies optional embedding-based speech answer comparison and its non-grading wording.
