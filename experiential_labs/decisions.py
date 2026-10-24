"""Minimal helper for the Decisions API shape, sent via the Experiential gateway.

GPT-6 Luna Decisions answers typed decision questions; it does not generate
chat completions. Results are advisory: this module never executes a returned
choice, merges a change, or bypasses review.
"""
import json
import os
import socket
import sys
import urllib.error
import urllib.request

DECISIONS_URL = "https://api.experientiallabs.ai/v1/decisions"
MODEL = "gpt-6-luna-decisions"
DEFAULT_TIMEOUT = 60  # seconds

# Experiential gateway admission bounds (not provider limits).
MAX_QUESTIONS = 32
MAX_CHOICES = 64
MIN_LEVELS, MAX_LEVELS = 2, 10

QUESTION_TYPES = ("predicate", "choice", "score")


class DecisionsError(Exception):
    """An HTTP or transport failure. The request may already have been charged."""


class MissingKeyError(DecisionsError):
    pass


def validate_questions(questions):
    if not isinstance(questions, list) or not questions:
        raise ValueError("questions must be a non-empty list")
    if len(questions) > MAX_QUESTIONS:
        raise ValueError(f"at most {MAX_QUESTIONS} questions per request")
    names = set()
    for i, q in enumerate(questions):
        if not q.get("instructions"):
            raise ValueError(f"question {i} needs instructions")
        qtype = q.get("type")
        if qtype not in QUESTION_TYPES:
            raise ValueError(f"question {i} type must be one of {QUESTION_TYPES}")
        name = q.get("name")
        if name is not None:
            if name in names:
                raise ValueError(f"duplicate question name {name!r}")
            names.add(name)
        if qtype == "choice":
            choices = q.get("choices") or []
            if not choices:
                raise ValueError(f"question {i} (choice) needs choices")
            if len(choices) > MAX_CHOICES:
                raise ValueError(f"question {i} has more than {MAX_CHOICES} choices")
        if qtype == "score":
            levels = q.get("levels") or []
            if not MIN_LEVELS <= len(levels) <= MAX_LEVELS:
                raise ValueError(
                    f"question {i} (score) needs {MIN_LEVELS}-{MAX_LEVELS} levels"
                )


def build_input(text, images=()):
    """Return plain text, or a message list when base64 images are attached.

    ``images`` is an iterable of (media_type, base64_data) pairs.
    """
    if not images:
        return text
    content = [{"type": "input_text", "text": text}]
    for media_type, b64 in images:
        content.append({
            "type": "input_image",
            "image_url": f"data:{media_type};base64,{b64}",
        })
    return [{"role": "user", "content": content}]


def decide(input, questions, api_key=None, timeout=DEFAULT_TIMEOUT):
    """POST one Decisions request. No retries: an unknown outcome may be charged."""
    api_key = api_key or os.environ.get("EXPERIENTIAL_API_KEY")
    if not api_key:
        raise MissingKeyError(
            "EXPERIENTIAL_API_KEY is not set. Please set it locally in your "
            "environment (do not paste it into chat)."
        )
    validate_questions(questions)
    body = json.dumps({"model": MODEL, "input": input, "questions": questions}).encode()
    req = urllib.request.Request(
        DECISIONS_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:2000]
        raise DecisionsError(f"HTTP {e.code} from decisions endpoint: {detail}") from e
    except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
        raise DecisionsError(
            f"Transport error calling decisions endpoint ({e}); outcome unknown, "
            "the request may already have been charged. Not retrying."
        ) from e


def answer_at(response, index):
    """Answers come back in question order; read by position."""
    answers = response.get("answers") or []
    if index >= len(answers):
        raise DecisionsError(f"response has no answer at position {index}")
    return answers[index]


def review_questions():
    """Questions for an advisory code-review decision. Index 0 is the review question."""
    return [
        {
            "name": "safe_to_merge",
            "type": "predicate",
            "instructions": "The change is correct and its tests adequately cover it.",
        },
        {
            "name": "risk",
            "type": "score",
            "instructions": "Rate the risk this change introduces.",
            "levels": [
                {"label": "low", "description": "Small, well-tested, isolated."},
                {"label": "medium", "description": "Some untested paths or wider impact."},
                {"label": "high", "description": "Likely to break behaviour or is untested."},
            ],
        },
        {
            "name": "next_step",
            "type": "choice",
            "instructions": "What should a human reviewer do next?",
            "choices": [
                {"value": "approve", "description": "Looks ready for human approval."},
                {"value": "request_changes", "description": "Needs fixes first."},
                {"value": "needs_more_tests", "description": "Add tests before review."},
            ],
        },
    ]


REVIEW_INDEX = 0


def format_answer(answer):
    if answer.get("refusal") or answer.get("type") == "refusal":
        return f"refused: {answer.get('refusal', 'model declined this question')}"
    fields = {k: v for k, v in answer.items() if k != "name"}
    label = answer.get("name", "(unnamed)")
    return f"{label}: {json.dumps(fields)}"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python -m experiential_labs.decisions DIFF_SUMMARY_FILE TEST_SUMMARY_FILE",
              file=sys.stderr)
        return 2
    with open(argv[0]) as f:
        diff_summary = f.read()
    with open(argv[1]) as f:
        test_summary = f.read()
    text = f"Diff summary:\n{diff_summary}\n\nTest summary:\n{test_summary}"
    try:
        response = decide(build_input(text), review_questions())
    except DecisionsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print("Advisory only; not a guarantee of correctness. Nothing was executed or merged.")
    print("Review decision:", format_answer(answer_at(response, REVIEW_INDEX)))
    for ans in (response.get("answers") or [])[1:]:
        print("  ", format_answer(ans))
    print("Usage:", json.dumps(response.get("usage")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
