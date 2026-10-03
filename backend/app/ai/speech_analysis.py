import re

from sentence_transformers import SentenceTransformer, util

from app.ai.speech_assessment import assess_answer


MODEL_NAME = "BAAI/bge-small-en-v1.5"

_embedding_model = SentenceTransformer(MODEL_NAME)


def _split_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"[.!?]+", text)
        if sentence.strip()
    ]


def _calculate_language_signals(text: str) -> dict:
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    sentences = _split_sentences(text)

    word_count = len(words)
    sentence_count = len(sentences)

    unique_words = len(set(words))

    average_sentence_length = (
        word_count / sentence_count
        if sentence_count
        else 0
    )

    vocabulary_diversity = (
        unique_words / word_count
        if word_count
        else 0
    )

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "unique_words": unique_words,
        "average_sentence_length": round(average_sentence_length, 2),
        "vocabulary_diversity": round(vocabulary_diversity, 3),
    }


def _estimate_cefr(signals: dict) -> dict:
    """
    Provides a rough CEFR-oriented estimate from basic language signals.
    Short transcripts are insufficient for even this heuristic estimate.
    """

    words = signals["word_count"]
    avg_sentence_length = signals["average_sentence_length"]
    vocabulary_diversity = signals["vocabulary_diversity"]

    if words < 30:
        return {
            "level": None,
            "sample_sufficient": False,
            "basis": "At least 30 transcript words are needed for this rough estimate; this is not a certified CEFR assessment.",
        }

    if avg_sentence_length < 7:
        level = "A2"
    elif (
        avg_sentence_length < 12
        and vocabulary_diversity < 0.55
    ):
        level = "B1"
    elif (
        avg_sentence_length < 18
        and vocabulary_diversity < 0.65
    ):
        level = "B2"
    else:
        level = "C1"

    return {
        "level": level,
        "sample_sufficient": True,
        "basis": "rough estimate from transcript sentence length and vocabulary variety; not a certified CEFR assessment",
    }


def _personalized_feedback(signals: dict, answer_relevance: dict | None) -> dict:
    strengths = []
    next_steps = []
    words = signals["word_count"]
    sentences = signals["sentence_count"]
    average_length = signals["average_sentence_length"]
    diversity = signals["vocabulary_diversity"]

    if sentences >= 2:
        strengths.append(f"You organized the response into {sentences} sentences.")
    if words >= 30:
        strengths.append("Your response provides enough transcript text to review language patterns.")

    if words < 25:
        next_steps.append("Expand your next response with a definition and one concrete example.")
    if average_length > 22:
        next_steps.append("Break long sentences into shorter steps so each idea is easier to follow.")
    if words >= 30 and diversity < 0.4:
        next_steps.append("Practice using a few precise alternatives for repeated key words.")
    if sentences < 2 and words >= 20:
        next_steps.append("Try a simple structure: state the idea, explain why, then give an example.")

    if answer_relevance:
        similarity = answer_relevance["similarity"]
        if similarity >= 0.75:
            strengths.append("Your response is semantically close to the reference provided.")
        elif similarity < 0.5:
            next_steps.append("Compare your response with the reference and restate the key concepts in your own words.")
        else:
            next_steps.append("Check which important idea from the reference could be explained more explicitly.")

    if not next_steps:
        next_steps.append("For your next practice, explain one key idea and support it with a specific example.")
    if not strengths:
        strengths.append("You completed a spoken response that can be reviewed and practiced again.")

    return {
        "strengths": strengths,
        "next_steps": next_steps,
        "basis": "Personalized practice suggestions derived from transcript length, sentence structure, vocabulary variation, and optional reference similarity.",
    }


def analyze_semantics(
    transcript: str,
    reference_text: str | None = None,
) -> dict:
    if not transcript or not transcript.strip():
        return {
            "mode": "semantic",
            "no_speech_detected": True,
            "message": "No clear speech was detected in your recording. Please speak clearly into your microphone or upload an audio file with spoken content.",
            "cefr_estimate": {
                "level": None,
                "sample_sufficient": False,
                "basis": "No spoken words detected in recording.",
            },
            "language_signals": {
                "word_count": 0,
                "sentence_count": 0,
                "unique_words": 0,
                "average_sentence_length": 0.0,
                "vocabulary_diversity": 0.0,
            },
            "personalized_feedback": {
                "strengths": [],
                "next_steps": ["Try recording your answer again in a quiet environment or upload a clear audio file."],
                "basis": "No speech detected in audio recording.",
            },
        }

    signals = _calculate_language_signals(transcript)

    result = {
        "mode": "semantic",
        "cefr_estimate": _estimate_cefr(signals),
        "language_signals": signals,
    }

    if reference_text and reference_text.strip():
        embeddings = _embedding_model.encode(
            [transcript, reference_text],
            normalize_embeddings=True,
        )

        similarity = util.cos_sim(
            embeddings[0],
            embeddings[1],
        ).item()

        similarity = round(float(similarity), 4)
        if similarity >= 0.75:
            interpretation = "The response is semantically close to the reference."
        elif similarity >= 0.50:
            interpretation = "The response shares some meaning with the reference; review the concepts it may have missed."
        else:
            interpretation = "The response differs from the reference; compare the key ideas before drawing a conclusion."
        result["answer_relevance"] = {
            "similarity": similarity,
            "interpretation": interpretation,
            "basis": "BGE sentence-embedding similarity; this is guidance, not a correctness grade.",
        }
        assessment = assess_answer(transcript, reference_text)
        result["answer_assessment"] = assessment or {
            "status": "unavailable",
            "message": "A reference-based answer judgment could not be generated. The meaning match is a separate similarity signal, not a correctness grade.",
        }

    result["personalized_feedback"] = _personalized_feedback(
        signals,
        result.get("answer_relevance"),
    )

    return result


# FILE PURPOSE:
# Analyzes speech transcripts with Sentence Transformers, transcript
# signals, reference relevance, and individualized practice suggestions.
