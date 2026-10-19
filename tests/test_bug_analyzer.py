from unittest.mock import patch
from analyzers.bug_analyzer import analyze_code


MOCK_AI_RESPONSE = {
    "success": True,
    "explanation": "Detected code issues and suggested improvements.",
    "why_it_happens": "Issues stem from mutable defaults and arithmetic zero division.",
    "suggested_fix": "Refactor defaults and validate divisors.",
    "corrected_code": "x = 10\nprint(x)",
    "changes_made": ["Fixed default argument", "Safeguarded division"],
}


@patch("analyzers.bug_analyzer.analyze_with_ai", return_value=MOCK_AI_RESPONSE)
def test_complete_analysis(mock_ai):
    code = """
import os

x = 10
y = 20

print(x)

def greet(name=[]):
    print(name)

try:
    print(x / 0)
except:
    pass
"""

    result = analyze_code(code)

    assert result["syntax"]["has_error"] is False
    assert result["ast"]["success"] is True

    assert "y" in result["static"]["unused_variables"]["findings"]
    assert "os" in result["static"]["unused_imports"]["findings"]
    assert len(result["static"]["mutable_defaults"]["findings"]) > 0
    assert len(result["static"]["bare_except"]["findings"]) > 0
    assert len(result["static"]["division_by_zero"]["findings"]) > 0

    assert result["static"]["unused_variables"]["explanation"]["title"] == "Unused Variable"
    assert result["static"]["division_by_zero"]["explanation"]["title"] == "Division by Zero"
    assert mock_ai.called


def test_invalid_syntax_stops_analysis():
    code = """
x = 10
print(x
"""

    result = analyze_code(code, enable_ai=False)

    assert result["syntax"]["has_error"] is True
    assert result["static"] == {}
    assert result["runtime"] is None


@patch("analyzers.bug_analyzer.analyze_with_ai", return_value=MOCK_AI_RESPONSE)
def test_none_comparison_in_complete_analysis(mock_ai):
    code = """
value = None

if value == None:
    print("No value")
"""

    result = analyze_code(code)

    assert result["syntax"]["has_error"] is False
    assert len(result["static"]["none_comparison"]["findings"]) == 1
    assert result["static"]["none_comparison"]["explanation"]["title"] == "None Comparison"


@patch("analyzers.bug_analyzer.analyze_with_ai", return_value=MOCK_AI_RESPONSE)
def test_runtime_error_explanation(mock_ai):
    code = """
x = 10
y = 0
print(x / y)
"""

    result = analyze_code(code)

    assert result["runtime"]["has_error"] is True
    assert result["runtime"]["error_type"] == "ZeroDivisionError"
    assert result["runtime"]["issue_type"] == "zero_division_error"
    assert result["runtime"]["line_number"] == 4
    assert result["runtime"]["source_line"] == "print(x / y)"

    assert result["runtime"]["explanation"]["title"] == "Zero Division Error"
    assert "divide" in result["runtime"]["explanation"]["description"]
    assert "divisor" in result["runtime"]["explanation"]["suggestion"]


@patch("analyzers.bug_analyzer.analyze_with_ai", return_value=MOCK_AI_RESPONSE)
def test_type_error_explanation(mock_ai):
    code = """
x = 10
print(x + "hello")
"""

    result = analyze_code(code)

    assert result["runtime"]["has_error"] is True
    assert result["runtime"]["error_type"] == "TypeError"
    assert result["runtime"]["issue_type"] == "type_error"
    assert result["runtime"]["line_number"] == 3
    assert result["runtime"]["source_line"] == 'print(x + "hello")'

    assert result["runtime"]["explanation"]["title"] == "Type Error at Runtime"