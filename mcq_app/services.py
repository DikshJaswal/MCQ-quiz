"""Question generation with Gemini, plus strict validation of what comes back.
The model's output is untrusted input: we parse it defensively, drop anything
malformed, and only ever render it through Django's auto-escaping templates.
"""
import json
import logging
import random
import re
from django.conf import settings

logger = logging.getLogger(__name__)
DIFFICULTIES = ("GATE", "University", "Interview")
MAX_QUESTION_LEN = 1000
MAX_OPTION_LEN = 300
MAX_EXPLANATION_LEN = 1200

class GenerationError(Exception):
    """Raised with a message that is safe to show to the user."""

def build_prompt(topic_name: str, subject_name: str, count: int) -> str:
    third = count // 3
    split = {"GATE": third, "Interview": third, "University": count - 2 * third}
    return (
        "You are an exam setter for Computer Science and Engineering courses.\n"
        f'Write {count} multiple-choice questions on the topic "{topic_name}" '
        f'from the subject "{subject_name}".\n'
        f"Difficulty mix: {split['GATE']} GATE-level, {split['University']} university "
        f"exam-level, {split['Interview']} technical-interview-level.\n\n"
        "Rules:\n"
        "- Exactly four options per question and exactly one correct option.\n"
        "- No 'all of the above' / 'none of the above' options.\n"
        "- Plain text only. No markdown, HTML or LaTeX.\n"
        "- Keep each option under 120 characters.\n"
        "- Include a short explanation (1 to 3 sentences) of why the correct option is right.\n\n"
        "Return ONLY a JSON array. Each item must look like:\n"
        '{"question": "...", "options": ["...", "...", "...", "..."], '
        '"answer_index": 0, "difficulty": "GATE", "explanation": "..."}\n'
        'where "answer_index" is the 0-based index of the correct option and '
        '"difficulty" is one of "GATE", "University", "Interview".'
    )

def _strip_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text

def _clean_text(value, max_len):
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    if not value or len(value) > max_len:
        return None
    return value

def _answer_index(item, options):
    idx = item.get("answer_index")
    if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(options):
        return idx
    answer = item.get("answer")
    if isinstance(answer, str):
        answer = " ".join(answer.split())
        if len(answer) == 1 and answer.upper() in "ABCD":
            return "ABCD".index(answer.upper())
        lowered = [o.lower() for o in options]
        if answer.lower() in lowered:
            return lowered.index(answer.lower())
    return None

def clean_question(item, rng=random):
    """Return a normalised question dict, or None if the item is unusable."""
    if not isinstance(item, dict):
        return None
    question = _clean_text(item.get("question"), MAX_QUESTION_LEN)
    raw_options = item.get("options")
    if not question or not isinstance(raw_options, list) or len(raw_options) != 4:
        return None
    options = [_clean_text(o, MAX_OPTION_LEN) for o in raw_options]
    if any(o is None for o in options) or len({o.lower() for o in options}) != 4:
        return None
    correct = _answer_index(item, options)
    if correct is None:
        return None
    difficulty = item.get("difficulty")
    difficulty = next(
        (d for d in DIFFICULTIES if isinstance(difficulty, str) and d.lower() == difficulty.strip().lower()),
        "University",
    )
    explanation = _clean_text(item.get("explanation"), MAX_EXPLANATION_LEN) or ""
    order = list(range(4))
    rng.shuffle(order)
    return {
        "question": question,
        "options": [options[i] for i in order],
        "answer": order.index(correct),
        "difficulty": difficulty,
        "explanation": explanation,
    }

def parse_questions(raw_text: str, rng=random):
    """Parse model output into a list of valid questions (possibly empty)."""
    try:
        data = json.loads(_strip_fences(raw_text or ""))
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, dict):
        data = data.get("questions", [])
    if not isinstance(data, list):
        return []
    questions = [q for q in (clean_question(item, rng) for item in data) if q]
    rng.shuffle(questions)
    return questions

def _call_gemini(prompt: str) -> str:
    from google import genai
    from google.genai import types
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_SECONDS * 1000),
    )
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.7,
        ),
    )
    return response.text or ""

def generate_questions(topic_name: str, subject_name: str):
    """Generate a quiz. Raises GenerationError with a user-safe message on failure."""
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not configured")
        raise GenerationError("Quiz generation isn't set up on this server yet.")
    count = settings.QUIZ_QUESTION_COUNT
    try:
        raw = _call_gemini(build_prompt(topic_name, subject_name, count))
    except Exception:  # network, quota, auth, SDK errors: log details, hide them from users
        logger.exception("Gemini request failed")
        raise GenerationError("We couldn't reach the question generator. Please try again in a moment.")
    questions = parse_questions(raw)
    if len(questions) < max(3, count // 2):
        logger.error("Gemini returned too few usable questions (%d of %d)", len(questions), count)
        raise GenerationError("The generator returned an incomplete quiz. Please try again.")
    return questions[:count]