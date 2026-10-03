import re


POSITIVE_WORDS = {
    "happy", "great", "good", "excellent", "love",
    "enjoy", "excited", "hope", "wonderful", "success",
    "confident", "proud", "calm", "helpful", "effective",
}

NEGATIVE_WORDS = {
    "sad", "bad", "hate", "angry", "frustrated",
    "difficult", "problem", "worried", "fear", "failure",
    "confused", "stress", "stressed", "disappointed",
    "frustrating", "frustrating", "poor", "weak", "wrong",
}

INTENSIFIERS = {
    "very", "really", "extremely", "highly", "so",
}

NEGATIONS = {
    "not", "never", "no", "neither", "hardly",
}


def analyze_tone(text: str) -> dict:
    if not text.strip():
        raise ValueError("Transcript cannot be empty.")

    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())

    positive_count = 0
    negative_count = 0

    for index, word in enumerate(words):
        previous_words = words[max(0, index - 2):index]

        is_negated = any(
            previous_word in NEGATIONS
            for previous_word in previous_words
        )

        is_intensified = any(
            previous_word in INTENSIFIERS
            for previous_word in previous_words
        )

        weight = 2 if is_intensified else 1

        if word in POSITIVE_WORDS:
            if is_negated:
                negative_count += weight
            else:
                positive_count += weight

        elif word in NEGATIVE_WORDS:
            if is_negated:
                positive_count += weight
            else:
                negative_count += weight

    total_signals = positive_count + negative_count

    if total_signals == 0:
        sentiment = "neutral"
    else:
        difference = positive_count - negative_count
        confidence = abs(difference) / total_signals

        if confidence < 0.20:
            sentiment = "mixed"
        elif difference > 0:
            sentiment = "positive"
        else:
            sentiment = "negative"

    return {
        "mode": "tone",
        "sentiment": sentiment,
        "positive_signals": positive_count,
        "negative_signals": negative_count,
    }


# FILE PURPOSE:
# Provides lightweight, explainable sentiment and tone analysis
# for speech transcripts using contextual word signals.

# FILE PURPOSE:
# Provides lightweight sentiment and tone analysis for speech transcripts.