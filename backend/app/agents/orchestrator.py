from pathlib import Path
from typing import Literal

from app.rag.answer import generate_rag_answer
from app.agents.quiz import generate_quiz
from app.ai.groq_search import create_groq_resource_agent
from app.ai.vision import analyze_image
from app.agents.resource import ResourceSearchError

AgentType = Literal["tutor", "quiz", "resource", "image", "speech"]


def classify_request(question: str) -> AgentType:
    normalized = question.lower().strip()
    quiz_keywords = {"quiz", "mcq", "multiple choice", "test me", "questions", "practice questions"}
    image_keywords = {
        "image", "photo", "picture", "diagram", "screenshot",
        "uploaded image", "analyze this image", "look at this image",
    }
    resource_keywords = {
        "latest", "today", "current", "recent", "news", "now", "this week", "this month",
        "2026", "search the web", "online", "internet", "resource", "resources",
        "library", "libraries", "study space", "study spaces", "college", "colleges",
        "training center", "training centre", "educational event", "workshop", "near me",
        "nearby", "search for", "find me", "present world",
    }
    if any(keyword in normalized for keyword in quiz_keywords):
        return "quiz"
    if any(keyword in normalized for keyword in image_keywords):
        return "image"
    if any(keyword in normalized for keyword in resource_keywords):
        return "resource"
    return "tutor"


def run_orchestrator(
    question: str,
    user_id: int,
    notebook_id: int,
    top_k: int = 3,
    image_path: str | Path | None = None,
    audio_path: str | Path | None = None,
    reference_text: str | None = None,
) -> dict:
    agent = (
        "speech" if audio_path is not None
        else "image" if image_path is not None
        else classify_request(question)
    )
    try:
        if agent == "resource":
            results = create_groq_resource_agent().search(question, max_results=5)
            return {
                "agent": "resource",
                "question": question,
                "results": [
                    {"title": result.title, "url": result.url, "snippet": result.snippet}
                    for result in results
                ],
            }
        if agent == "tutor":
            return {
                "agent": "tutor",
                **generate_rag_answer(
                    question=question,
                    user_id=user_id,
                    notebook_id=notebook_id,
                    top_k=top_k,
                ),
            }
        if agent == "image":
            if image_path is None:
                return {"agent": "image", "question": question, "answer": "Upload an image to ask the Image Agent about it."}
            return {
                "agent": "image",
                "question": question,
                "answer": analyze_image(file_path=image_path, question=question),
            }
        if agent == "speech":
            if audio_path is None:
                return {"agent": "speech", "message": "Upload an audio recording to use Speech Analysis."}
            from app.ai.speech import transcribe_audio
            from app.ai.speech_analysis import analyze_semantics
            from app.ai.speech_tone import analyze_tone
            transcript = transcribe_audio(file_path=audio_path)
            return {
                "agent": "speech",
                "transcript": transcript,
                "semantic_analysis": analyze_semantics(transcript=transcript, reference_text=reference_text),
                "tone_analysis": analyze_tone(text=transcript),
            }
        return {
            "agent": "quiz",
            **generate_quiz(topic=question, user_id=user_id, notebook_id=notebook_id, top_k=top_k),
        }
    except ResourceSearchError:
        raise
    except Exception as exc:
        raise RuntimeError(f"{agent} agent failed while processing the request.") from exc


# Routes user requests to tutor, quiz, Groq web search, image, and speech.
