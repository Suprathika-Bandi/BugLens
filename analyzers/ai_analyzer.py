import ast
import json
import os
import socket
import urllib.error
import urllib.request


DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"
DEFAULT_TIMEOUT = 120


def get_ollama_url():
    """Return the configured Ollama URL."""
    return os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)


def get_ollama_model():
    """Return the configured Ollama model."""
    return os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)


def extract_json(text):
    """Extract a JSON object from an AI response."""
    if not text:
        return None

    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)

        if isinstance(data, dict):
            return data

    except (json.JSONDecodeError, ValueError):
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            data = json.loads(candidate)

            if isinstance(data, dict):
                return data

        except (json.JSONDecodeError, ValueError):
            pass

    return None


def format_detected_issues(detected_issues):
    """Convert BugLens findings into concise text for Ollama."""
    if not detected_issues:
        return "No issues were detected."

    if isinstance(detected_issues, str):
        return detected_issues

    lines = []

    if isinstance(detected_issues, dict):

        for issue_type, issue_data in detected_issues.items():

            if isinstance(issue_data, dict):
                findings = issue_data.get("findings", [])

                if findings:
                    lines.append(f"- {issue_type}: {findings}")

            elif isinstance(issue_data, list):

                if issue_data:
                    lines.append(f"- {issue_type}: {issue_data}")

            else:
                lines.append(f"- {issue_type}: {issue_data}")

        return "\n".join(lines) if lines else "No issues were detected."

    if isinstance(detected_issues, list):

        for index, item in enumerate(detected_issues, start=1):

            if isinstance(item, dict):

                category = item.get("category", "")
                severity = item.get("severity", "")

                message = (
                    item.get("message")
                    or item.get("description")
                    or str(item)
                )

                line = item.get("line") or item.get("line_number")

                prefix = f"[{severity}] " if severity else ""
                category_text = f"{category}: " if category else ""
                line_text = f" (line {line})" if line else ""

                lines.append(
                    f"{index}. {prefix}{category_text}"
                    f"{message}{line_text}"
                )

            else:
                lines.append(f"{index}. {item}")

        return "\n".join(lines)

    return str(detected_issues)


def _validate_corrected_code(corrected_code):
    """
    Validate that AI-generated corrected code is at least valid Python.

    This does NOT execute the generated code.
    """
    if not corrected_code or not corrected_code.strip():
        return False, "AI did not provide corrected code."

    try:
        ast.parse(corrected_code)
        return True, ""
    except SyntaxError as exc:
        return False, f"Corrected code has a syntax error: {exc}"


def _safe_result(data):
    """Normalize Ollama's JSON into the BugLens AI result structure."""

    if not isinstance(data, dict):
        return {
            "success": False,
            "error": "AI returned an unexpected response format.",
        }

    explanation = str(data.get("explanation", "")).strip()
    why_it_happens = str(data.get("why_it_happens", "")).strip()
    suggested_fix = str(data.get("suggested_fix", "")).strip()
    corrected_code = str(data.get("corrected_code", "")).strip()

    changes = data.get("changes_made", [])

    if isinstance(changes, str):
        changes = [changes]

    elif not isinstance(changes, list):
        changes = [str(changes)]

    changes = [str(change).strip() for change in changes if str(change).strip()]

    valid, validation_error = _validate_corrected_code(corrected_code)

    if not valid:
        return {
            "success": False,
            "error": validation_error,
            "explanation": explanation,
            "why_it_happens": why_it_happens,
            "suggested_fix": suggested_fix,
            "corrected_code": corrected_code,
            "changes_made": changes,
        }

    return {
        "success": True,
        "explanation": explanation,
        "why_it_happens": why_it_happens,
        "suggested_fix": suggested_fix,
        "corrected_code": corrected_code,
        "changes_made": changes,
    }


def analyze_with_ai(code, detected_issues=None):
    """
    Analyze Python code with the local Ollama model.

    Ollama is responsible for explaining BugLens findings and suggesting
    minimal corrections. Deterministic BugLens analysis remains authoritative.
    """

    if detected_issues is None:
        detected_issues = {}

    url = get_ollama_url()
    model = get_ollama_model()

    issues_text = format_detected_issues(detected_issues)

    code_trimmed = code.strip()

    if len(code_trimmed) > 1200:
        code_trimmed = (
            code_trimmed[:1200]
            + "\n# ... remaining code omitted from AI prompt ..."
        )

    prompt = f"""
You are the AI explanation and code-fix assistant inside BugLens.

Your job is to explain the bugs that BugLens has already detected and provide
a MINIMAL correction to the supplied Python code.

IMPORTANT RULES:

1. BugLens's detected issues are authoritative.
2. Address the detected issues, but do not invent unrelated bugs.
3. Make the smallest reasonable changes necessary.
4. Preserve the original variable values, function names, program structure,
   and intended behavior whenever possible.
5. Do not change values just to make the code look different.
6. Do not remove working code unless it is directly related to a detected issue.
7. Never add "return" at the top level of a Python script.
8. Never claim that you removed something unless it is actually removed.
9. Never claim that you added something unless it is actually present.
10. The corrected_code MUST be complete standalone Python code.
11. The corrected_code MUST be syntactically valid Python.
12. Keep print() if it is necessary for the demonstrated program behavior.
13. If print() is only a code-hygiene issue, you may remove it, but then
    accurately describe that change.
14. Do not invent requirements such as returning values from functions unless
    that is necessary to fix a detected problem.
15. Do not rewrite the entire program.
16. changes_made must describe ONLY changes actually present in corrected_code.
17. Return ONLY valid JSON. Do not use Markdown around the JSON.

PYTHON CODE:
{code_trimmed}

BUGLENS DETECTED ISSUES:
{issues_text}

Return exactly these JSON keys:

{{
  "explanation": "What is wrong with the code.",
  "why_it_happens": "Why the detected issue happens.",
  "suggested_fix": "What should be changed.",
  "corrected_code": "Complete corrected Python code.",
  "changes_made": [
    "Only actual changes made to corrected_code."
  ]
}}
""".strip()

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 300,
        },
    }

    try:

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        accumulated = []

        with urllib.request.urlopen(
            request,
            timeout=DEFAULT_TIMEOUT,
        ) as response:

            for raw_line in response:

                chunk = json.loads(
                    raw_line.decode("utf-8")
                )

                token = chunk.get("response", "")

                if token:
                    accumulated.append(token)

                if chunk.get("done", False):
                    break

        raw_response = "".join(accumulated).strip()

        if not raw_response:
            return {
                "success": False,
                "error": "AI returned an empty response.",
            }

        parsed = extract_json(raw_response)

        if parsed is None:
            return {
                "success": False,
                "error": "AI returned an invalid JSON response.",
                "raw_response": raw_response,
            }

        return _safe_result(parsed)

    except urllib.error.HTTPError as error:

        if error.code == 404:
            return {
                "success": False,
                "error": (
                    f"Ollama model '{model}' was not found. "
                    f"Run: ollama pull {model}"
                ),
            }

        return {
            "success": False,
            "error": f"Ollama HTTP error: {error.code} {error.reason}",
        }

    except urllib.error.URLError as error:

        reason = error.reason

        if (
            isinstance(reason, (TimeoutError, socket.timeout))
            or "timed out" in str(reason).lower()
        ):
            return {
                "success": False,
                "error": (
                    f"AI analysis timed out after "
                    f"{DEFAULT_TIMEOUT} seconds. "
                    f"Deterministic BugLens analysis is still complete."
                ),
            }

        return {
            "success": False,
            "error": (
                "Ollama is not running. Make sure Ollama is running "
                "at http://localhost:11434."
            ),
        }

    except (TimeoutError, socket.timeout):

        return {
            "success": False,
            "error": (
                f"AI analysis timed out after "
                f"{DEFAULT_TIMEOUT} seconds. "
                f"Deterministic BugLens analysis is still complete."
            ),
        }

    except Exception as error:

        return {
            "success": False,
            "error": f"AI analysis failed: {error}",
        }