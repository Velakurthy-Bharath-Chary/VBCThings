import json
import re

from pydantic import BaseModel, Field, ValidationError

from app.ai.llm import generate_answer
from app.rag.query import query_rag


SYSTEM_PROMPT = """
You are the VBC Things Quiz Agent.

Generate a quiz using ONLY the provided notebook context.

Return EXACTLY 5 multiple-choice questions.

Your response MUST be valid JSON.
Do not use Markdown.
Do not use code fences.
Do not add any text before or after the JSON.

JSON format:

{
  "questions": [
    {
      "question": "Question text",
      "options": {
        "A": "Option A",
        "B": "Option B",
        "C": "Option C",
        "D": "Option D"
      },
      "correct_answer": "A",
      "explanation": "Short explanation"
    }
  ]
}

Rules:
1. Create exactly 5 questions.
2. Each question must have exactly 4 options: A, B, C, D.
3. correct_answer must be A, B, C, or D.
4. The correct answer must be supported by the notebook context.
5. Explanations must be supported by the notebook context.
6. Do not use outside knowledge.
"""


class QuizQuestion(BaseModel):
    question: str
    options: dict[str, str] = Field(min_length=4, max_length=4)
    correct_answer: str
    explanation: str


class QuizResponse(BaseModel):
    questions: list[QuizQuestion] = Field(min_length=1, max_length=20)


def _parse_quiz_response(raw_response: str) -> dict:
    cleaned = raw_response.strip()

    # Remove Markdown code fences.
    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # Extract JSON string if wrapped in extra text.
    match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("Quiz Agent returned invalid JSON.") from exc

    if isinstance(parsed, dict) and "questions" in parsed and isinstance(parsed["questions"], list):
        normalized_questions = []
        for q in parsed["questions"]:
            if not isinstance(q, dict):
                continue
            question_text = str(q.get("question", "")).strip()
            raw_options = q.get("options", {})
            if not isinstance(raw_options, dict):
                continue

            # Normalize option keys to uppercase A, B, C, D
            norm_options = {}
            for k, v in raw_options.items():
                clean_k = str(k).strip().upper().rstrip(".")
                if clean_k in {"A", "B", "C", "D"}:
                    norm_options[clean_k] = str(v).strip()

            correct = str(q.get("correct_answer", "")).strip().upper().rstrip(".")
            if correct not in {"A", "B", "C", "D"}:
                # Try finding correct answer from option values or text
                for opt_k, opt_v in norm_options.items():
                    if correct in opt_v.upper() or opt_v.upper() in correct:
                        correct = opt_k
                        break
                if correct not in {"A", "B", "C", "D"}:
                    correct = "A"

            explanation = str(q.get("explanation", "")).strip() or "Supported by the notebook sources."

            if question_text and len(norm_options) == 4:
                normalized_questions.append({
                    "question": question_text,
                    "options": norm_options,
                    "correct_answer": correct,
                    "explanation": explanation,
                })

        if normalized_questions:
            parsed["questions"] = normalized_questions[:5]

    try:
        validated = QuizResponse.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("Quiz Agent returned invalid structured output.") from exc

    return validated.model_dump()


def generate_quiz(
    topic: str,
    user_id: int,
    notebook_id: int,
    top_k: int = 5,
) -> dict:
    rag_result = query_rag(
        question=topic,
        user_id=user_id,
        notebook_id=notebook_id,
        top_k=top_k,
    )

    results = rag_result["results"]

    if not results:
        return {
            "topic": topic,
            "questions": [],
            "message": "I couldn't find enough information in the uploaded sources.",
        }

    context = "\n\n".join(
        f"Source: {result['source']}\n"
        f"Content: {result['text']}"
        for result in results
    )

    user_prompt = f"""
Notebook context:

{context}

Create a 5-question MCQ quiz about:

{topic}
"""

    raw_quiz = generate_answer(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    quiz = _parse_quiz_response(raw_quiz)

    return {
        "topic": topic,
        "quiz": quiz,
        "sources": [
            {
                "source": result["source"],
                "chunk_index": result["chunk_index"],
            }
            for result in results
        ],
    }


# FILE PURPOSE:
# Generates validated, notebook-grounded, structured MCQ quizzes.
