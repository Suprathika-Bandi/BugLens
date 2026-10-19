import json
import os
from unittest.mock import patch, MagicMock

from app import app
from analyzers.ai_analyzer import get_ollama_model, get_ollama_url
from analyzers.bug_analyzer import analyze_code, _calculate_health_score
from analyzers.runtime_analyzer import analyze_runtime
from analyzers.static_analyzer import (
    find_broad_except,
    find_dangerous_exec,
    find_shadowed_builtins,
    find_suspicious_conditions,
)


# =========================================================================
# 1. New Static Analysis Rule Tests
# =========================================================================

def test_suspicious_condition_constant():
    code = """
if True:
    print("Always runs")
"""
    results = find_suspicious_conditions(code)
    assert len(results) == 1
    assert "constant literal" in results[0]["message"].lower()


def test_suspicious_condition_self_compare():
    code = """
x = 10
if x == x:
    print("Self compare")
"""
    results = find_suspicious_conditions(code)
    assert len(results) == 1
    assert "compared against itself" in results[0]["message"].lower()


def test_shadowed_builtins():
    code = """
list = [1, 2, 3]
dict = {"a": 1}
"""
    results = find_shadowed_builtins(code)
    shadowed_vars = [r["variable"] for r in results]
    assert "list" in shadowed_vars
    assert "dict" in shadowed_vars


def test_dangerous_exec():
    code = """
user_str = "print('hello')"
exec(user_str)
"""
    results = find_dangerous_exec(code)
    assert len(results) == 1
    assert results[0]["line"] == 3


def test_broad_except():
    code = """
try:
    x = 1
except Exception:
    pass
"""
    results = find_broad_except(code)
    assert len(results) == 1
    assert results[0]["line"] == 4


# =========================================================================
# 2. Health Score and Results Model Tests
# =========================================================================

def test_health_score_calculation_clean():
    score, rating = _calculate_health_score([], False)
    assert score == 100
    assert rating == "Excellent"


def test_health_score_calculation_syntax_error():
    score, rating = _calculate_health_score([], True)
    assert score == 0
    assert rating == "Critical"


def test_health_score_deductions():
    issues = [
        {"severity": "CRITICAL"},
        {"severity": "HIGH"},
        {"severity": "MEDIUM"},
    ]
    # 100 - 25 - 15 - 8 = 52
    score, rating = _calculate_health_score(issues, False)
    assert score == 52
    assert rating == "Fair"


def test_analyze_code_empty_without_ai():
    result = analyze_code("", enable_ai=False)
    assert result["syntax"]["has_error"] is False
    assert result["summary"]["health_score"] == 100
    assert result["ai_analysis"] is None


def test_analyze_code_fast_without_ai():
    code = """
def test():
    x = 10
    y = 20
    return x
"""
    result = analyze_code(code, enable_ai=False)
    assert result["syntax"]["has_error"] is False
    assert result["summary"]["total_issues"] > 0
    assert result["ai_analysis"] is None
    assert result["summary"]["ai_status"] == "Disabled"


# =========================================================================
# 3. Runtime Error Mapping & Regression Tests
# =========================================================================

def test_runtime_index_error():
    code = """
items = [1, 2]
print(items[10])
"""
    result = analyze_runtime(code)
    assert result["has_error"] is True
    assert result["error_type"] == "IndexError"
    assert result["issue_type"] == "index_error"


def test_runtime_key_error():
    code = """
data = {"a": 1}
print(data["nonexistent"])
"""
    result = analyze_runtime(code)
    assert result["has_error"] is True
    assert result["error_type"] == "KeyError"
    assert result["issue_type"] == "key_error"


def test_runtime_attribute_error():
    code = """
num = 42
num.nonexistent_method()
"""
    result = analyze_runtime(code)
    assert result["has_error"] is True
    assert result["error_type"] == "AttributeError"
    assert result["issue_type"] == "attribute_error"


def test_runtime_name_error_message_preservation():
    """
    REGRESSION TEST:
    Verify that runtime errors preserve the actual Python exception message
    (e.g., NameError: name 'z' is not defined) and NEVER format as 'NameError: None'.
    """
    code = "print(z)"
    result = analyze_code(code, enable_ai=False)

    assert result["runtime"]["has_error"] is True
    assert result["runtime"]["error_type"] == "NameError"
    assert "name 'z' is not defined" in result["runtime"]["exception_message"]

    # Verify unified issue messages never show 'NameError: None'
    issue_messages = [i["message"] for i in result["issues"]]
    assert "NameError: None" not in issue_messages
    assert any("NameError: name 'z' is not defined" in msg for msg in issue_messages)


# =========================================================================
# 4. Flask API Endpoint Tests (Deterministic & Async AI)
# =========================================================================

def test_api_status_endpoint():
    client = app.test_client()
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert "ollama" in data
    assert "endpoint" in data["ollama"]
    assert "target_model" in data["ollama"]
    assert "generation_status" in data["ollama"]


def test_api_analyze_valid_code():
    client = app.test_client()
    payload = {
        "code": "x = 10\nprint(x)",
        "enable_ai": False,
    }
    response = client.post(
        "/api/analyze",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "result" in data
    assert data["result"]["syntax"]["has_error"] is False


def test_api_analyze_empty_code():
    client = app.test_client()
    payload = {"code": "   "}
    response = client.post(
        "/api/analyze",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "error" in data


def test_api_analyze_syntax_error():
    client = app.test_client()
    payload = {
        "code": "def broken_syntax(\n",
        "enable_ai": False,
    }
    response = client.post(
        "/api/analyze",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["result"]["syntax"]["has_error"] is True
    assert data["result"]["summary"]["health_score"] == 0


@patch("app.analyze_with_ai")
def test_api_analyze_ai_success(mock_ai):
    mock_ai.return_value = {
        "success": True,
        "explanation": "Zero division detected",
        "why_it_happens": "Divisor is zero",
        "suggested_fix": "Check divisor before dividing",
        "corrected_code": "if y != 0: print(x / y)",
        "changes_made": ["Added zero check"],
    }
    client = app.test_client()
    payload = {
        "code": "x = 10\ny = 0\nprint(x / y)",
        "detected_issues": [{"category": "Arithmetic", "message": "ZeroDivisionError"}],
    }
    response = client.post(
        "/api/analyze-ai",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["ai_analysis"]["explanation"] == "Zero division detected"
    assert data["ai_analysis"]["corrected_code"] == "if y != 0: print(x / y)"


def test_api_analyze_ai_empty_code():
    client = app.test_client()
    payload = {"code": ""}
    response = client.post(
        "/api/analyze-ai",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False


# =========================================================================
# 5. Environment Variables & AI Configuration Tests
# =========================================================================

def test_ollama_environment_defaults():
    with patch.dict(os.environ, {}, clear=True):
        assert get_ollama_model() == "llama3.2"
        assert get_ollama_url() == "http://localhost:11434/api/generate"


def test_ollama_environment_custom():
    custom_env = {
        "OLLAMA_MODEL": "custom-coder:3b",
        "OLLAMA_URL": "http://192.168.1.100:11434/api/generate",
    }
    with patch.dict(os.environ, custom_env, clear=True):
        assert get_ollama_model() == "custom-coder:3b"
        assert get_ollama_url() == "http://192.168.1.100:11434/api/generate"
