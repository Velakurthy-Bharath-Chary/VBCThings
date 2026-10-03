import logging
from functools import lru_cache
from typing import Iterator

from groq import Groq

from app.config import settings


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client() -> Groq:
    if not settings.groq_api_key.strip():
        raise RuntimeError("GROQ_API_KEY is not configured.")
    return Groq(api_key=settings.groq_api_key)


def generate_answer(system_prompt: str, user_prompt: str) -> str:
    try:
        response = _client().chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            raise RuntimeError("Groq returned an empty response.")
        return answer
    except Exception as exc:
        logger.exception("Groq text generation failed.")
        raise RuntimeError("The language model is currently unavailable.") from exc


def generate_answer_stream(system_prompt: str, user_prompt: str) -> Iterator[str]:
    try:
        response = _client().chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            stream=True,
        )
        emitted = False
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                emitted = True
                yield chunk.choices[0].delta.content
        if not emitted:
            raise RuntimeError("Groq returned an empty response stream.")
    except Exception as exc:
        logger.exception("Groq response streaming failed.")
        raise RuntimeError("Language-model response streaming failed.") from exc


# Uses one Groq client for streaming and non-streaming generation.
