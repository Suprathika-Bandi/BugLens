from unittest.mock import patch
from app import app


def test_home_page():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"BugLens" in response.data


@patch("analyzers.bug_analyzer.analyze_with_ai")
def test_code_analysis(mock_ai):
    mock_ai.return_value = {
        "success": True,
        "explanation": "Clean execution",
        "why_it_happens": "",
        "suggested_fix": "",
        "corrected_code": "x = 10\nprint(x)",
        "changes_made": [],
    }
    client = app.test_client()

    code = """
x = 10
print(x)
"""

    response = client.post(
        "/",
        data={"code": code}
    )

    assert response.status_code == 200
    assert b"No syntax errors found" in response.data
    assert b"AST analysis completed successfully" in response.data