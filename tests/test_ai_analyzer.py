"""
Tests for analyzers/ai_analyzer.py

The analyzer uses streaming mode (stream:true), so Ollama sends one JSON line
per token. Mocks must return an iterable of bytes lines (not response.read()).
"""
import json
import socket
import urllib.error
from unittest.mock import MagicMock, patch

from analyzers.ai_analyzer import analyze_with_ai, extract_json, format_detected_issues


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_streaming_response(text_payload: str):
    """
    Build a mock urlopen context manager that mimics Ollama's streaming output.

    Splits text_payload into tokens and yields them as individual JSON-lines,
    followed by a final done=True line — exactly as the real Ollama API does.
    """
    # Produce one token per character to exercise the accumulation loop,
    # then signal done.
    chunks = []
    for char in text_payload:
        chunks.append(
            json.dumps({"model": "llama3.2", "response": char, "done": False}).encode("utf-8")
        )
    chunks.append(
        json.dumps({"model": "llama3.2", "response": "", "done": True}).encode("utf-8")
    )

    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=iter(chunks))
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# extract_json
# ---------------------------------------------------------------------------

def test_extract_json_valid():
    text = '{"explanation": "test", "why_it_happens": "test", "suggested_fix": "fix", "corrected_code": "code", "changes_made": []}'
    result = extract_json(text)
    assert result is not None
    assert result["explanation"] == "test"


def test_extract_json_markdown_fence():
    text = '```json\n{"explanation": "test", "why_it_happens": "test", "suggested_fix": "fix", "corrected_code": "code", "changes_made": []}\n```'
    result = extract_json(text)
    assert result is not None
    assert result["explanation"] == "test"


def test_extract_json_invalid():
    assert extract_json("not a json string") is None
    assert extract_json("") is None


# ---------------------------------------------------------------------------
# format_detected_issues
# ---------------------------------------------------------------------------

def test_format_detected_issues():
    assert "No issues" in format_detected_issues({})
    formatted = format_detected_issues({"unused_variables": ["y"]})
    assert "unused_variables" in formatted


# ---------------------------------------------------------------------------
# analyze_with_ai — happy path
# ---------------------------------------------------------------------------

@patch("urllib.request.urlopen")
def test_ollama_available_valid_response(mock_urlopen):
    payload = json.dumps({
        "explanation": "Variables unused",
        "why_it_happens": "y is never read",
        "suggested_fix": "Remove y",
        "corrected_code": "x = 10",
        "changes_made": ["Removed y"],
    })
    mock_urlopen.return_value = _make_streaming_response(payload)

    code = "x = 10\ny = 20"
    issues = {"unused_variables": ["y"]}
    result = analyze_with_ai(code, issues)

    assert result["success"] is True
    assert result["explanation"] == "Variables unused"
    assert result["why_it_happens"] == "y is never read"
    assert result["suggested_fix"] == "Remove y"
    assert result["corrected_code"] == "x = 10"
    assert result["changes_made"] == ["Removed y"]


@patch("urllib.request.urlopen")
def test_code_with_no_detected_issues(mock_urlopen):
    payload = json.dumps({
        "explanation": "No known issues detected.",
        "why_it_happens": "N/A",
        "suggested_fix": "N/A",
        "corrected_code": "x = 10",
        "changes_made": [],
    })
    mock_urlopen.return_value = _make_streaming_response(payload)

    result = analyze_with_ai("x = 10", {})
    assert result["success"] is True
    assert "No known issues" in result["explanation"]


# ---------------------------------------------------------------------------
# analyze_with_ai — empty / invalid responses
# ---------------------------------------------------------------------------

@patch("urllib.request.urlopen")
def test_empty_ai_response(mock_urlopen):
    """Streaming returns only whitespace/empty tokens → empty accumulated string."""
    chunks = [
        json.dumps({"response": "   ", "done": False}).encode("utf-8"),
        json.dumps({"response": "", "done": True}).encode("utf-8"),
    ]
    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=iter(chunks))
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    result = analyze_with_ai("x = 1", {})
    assert result["success"] is False
    assert "empty response" in result["error"]


@patch("urllib.request.urlopen")
def test_invalid_json_ai_response(mock_urlopen):
    """Streaming yields non-JSON text → invalid JSON response error."""
    mock_urlopen.return_value = _make_streaming_response("this is not json")

    result = analyze_with_ai("x = 1", {})
    assert result["success"] is False
    assert "invalid JSON response" in result["error"]


# ---------------------------------------------------------------------------
# analyze_with_ai — connection errors
# ---------------------------------------------------------------------------

@patch("urllib.request.urlopen")
def test_ollama_unavailable(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.URLError(reason=ConnectionRefusedError("Connection refused"))

    result = analyze_with_ai("x = 1", {})
    assert result["success"] is False
    assert "Ollama is not running" in result["error"]


@patch("urllib.request.urlopen")
def test_ollama_timeout(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.URLError(reason=socket.timeout("timed out"))

    result = analyze_with_ai("x = 1", {})
    assert result["success"] is False
    assert "timed out" in result["error"].lower()


@patch("urllib.request.urlopen")
def test_ollama_model_not_found(mock_urlopen):
    err = urllib.error.HTTPError(url="", code=404, msg="Not Found", hdrs={}, fp=None)
    mock_urlopen.side_effect = err

    result = analyze_with_ai("x = 1", {})
    assert result["success"] is False
    assert "was not found" in result["error"]


# ---------------------------------------------------------------------------
# analyze_with_ai — unexpected exception
# ---------------------------------------------------------------------------

@patch("urllib.request.urlopen")
def test_generic_exception(mock_urlopen):
    mock_urlopen.side_effect = RuntimeError("Something blew up")

    result = analyze_with_ai("x = 1", {})
    assert result["success"] is False
    assert "AI analysis failed" in result["error"]
