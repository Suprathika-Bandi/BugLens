import json
import os
import socket
import urllib.error
import urllib.request

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"
DEFAULT_TIMEOUT = 30  # 30 seconds max — covers cold model load (~24s) + warm requests (~2-4s)


def get_ollama_url():
    """Return the configured Ollama URL."""
    return os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)


def get_ollama_model():
    """Return the configured Ollama model."""
    return os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)


def extract_json(text):
    """
    Extract a JSON object from an AI response.
    Handles raw JSON, markdown code blocks, and embedded JSON objects.
    """
    if not text:
        return None

    text = text.strip()

    # Strip markdown code fence if wrapped
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Search for first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def format_detected_issues(detected_issues):
    """
    Convert detected issues into clean concise text for the AI prompt.
    Supports dictionaries (like static analysis dict), lists of issue dicts, or strings.
    """
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

        if not lines:
            return "No issues were detected."
        return "\n".join(lines)

    if isinstance(detected_issues, list):
        for index, item in enumerate(detected_issues, start=1):
            if isinstance(item, dict):
                category = item.get("category", "")
                severity = item.get("severity", "")
                message = item.get("message") or item.get("description") or str(item)
                line = item.get("line") or item.get("line_number")

                prefix = f"[{severity}] " if severity else ""
                cat_str = f"{category}: " if category else ""
                line_str = f" (line {line})" if line else ""
                lines.append(f"{index}. {prefix}{cat_str}{message}{line_str}")
            else:
                lines.append(f"{index}. {item}")

        return "\n".join(lines)

    return str(detected_issues)


def _safe_result(data):
    """Normalize the parsed JSON data into standard BugLens AI structure."""
    if not isinstance(data, dict):
        return {
            "success": False,
            "error": "AI returned an unexpected response format.",
        }

    changes = data.get("changes_made", [])
    if isinstance(changes, str):
        changes = [changes]
    elif not isinstance(changes, list):
        changes = [str(changes)]

    return {
        "success": True,
        "explanation": str(data.get("explanation", "")).strip(),
        "why_it_happens": str(data.get("why_it_happens", "")).strip(),
        "suggested_fix": str(data.get("suggested_fix", "")).strip(),
        "corrected_code": str(data.get("corrected_code", "")).strip(),
        "changes_made": [str(c) for c in changes if c],
    }


def analyze_with_ai(code, detected_issues=None):
    """
    Send source code and detected issues to local Ollama model for analysis.

    Uses STREAMING mode (stream:true) so Ollama sends one JSON line per token.
    Each arriving chunk resets the socket read timeout, so the per-chunk timeout
    fires only if generation stalls — not because Ollama is still thinking.
    This avoids the "timed out after 30s" problem that occurs with stream:false
    (where Ollama holds the connection open until all tokens are generated before
    sending any bytes).

    Returns structured result and never raises unhandled exceptions.
    """
    if detected_issues is None:
        detected_issues = {}

    url = get_ollama_url()
    model = get_ollama_model()
    issues_text = format_detected_issues(detected_issues)

    # Trim code to avoid huge prompts blowing the context window
    code_trimmed = code.strip()
    if len(code_trimmed) > 800:
        code_trimmed = code_trimmed[:800] + "\n# ... (truncated)"

    prompt = (
        f"Analyze this buggy Python code and return ONLY a JSON object.\n\n"
        f"CODE:\n{code_trimmed}\n\n"
        f"ISSUES: {issues_text}\n\n"
        f'Return JSON with keys: "explanation" (str), "why_it_happens" (str), '
        f'"suggested_fix" (str), "corrected_code" (str), "changes_made" (list of str).'
    )

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,          # STREAMING: each token arrives as a line — no bulk-wait timeout
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 400,
        },
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        accumulated = []
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as response:
            # Each line is a JSON object: {"model":...,"response":"<token>","done":bool}
            for raw_line in response:
                chunk = json.loads(raw_line.decode("utf-8"))
                token = chunk.get("response", "")
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
                "explanation": raw_response,
            }

        return _safe_result(parsed)

    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {
                "success": False,
                "error": f"Ollama model '{model}' was not found. Run: ollama pull {model}",
            }
        return {
            "success": False,
            "error": f"Ollama HTTP error: {error.code} {error.reason}",
        }

    except urllib.error.URLError as error:
        reason = error.reason
        if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(reason).lower():
            return {
                "success": False,
                "error": (
                    f"AI analysis timed out. Ollama is running but a token gap exceeded "
                    f"{DEFAULT_TIMEOUT} seconds. Deterministic BugLens analysis is still complete."
                ),
            }
        return {
            "success": False,
            "error": "Ollama is not running. Make sure Ollama is running at http://localhost:11434 (run 'ollama serve').",
        }

    except (TimeoutError, socket.timeout):
        return {
            "success": False,
            "error": (
                f"AI analysis timed out. Ollama is running but a token gap exceeded "
                f"{DEFAULT_TIMEOUT} seconds. Deterministic BugLens analysis is still complete."
            ),
        }

    except Exception as error:
        return {
            "success": False,
            "error": f"AI analysis failed: {error}",
        }