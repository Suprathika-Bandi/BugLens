from analyzers.ai_analyzer import analyze_with_ai
from analyzers.ast_analyzer import analyze_ast
from analyzers.explanation_engine import get_explanation
from analyzers.runtime_analyzer import analyze_runtime
from analyzers.static_analyzer import (
    find_bare_except,
    find_broad_except,
    find_dangerous_eval,
    find_dangerous_exec,
    find_debug_prints,
    find_division_by_zero,
    find_mutable_defaults,
    find_none_comparison,
    find_shadowed_builtins,
    find_suspicious_conditions,
    find_undefined_variables,
    find_unreachable_code,
    find_unused_imports,
    find_unused_variables,
)
from analyzers.syntax_analyzer import analyze_syntax


SEVERITY_WEIGHTS = {
    "CRITICAL": 25,
    "HIGH": 15,
    "MEDIUM": 8,
    "LOW": 3,
    "INFO": 1,
}


def _calculate_health_score(issues, has_syntax_error):
    """
    Calculate an objective code health score between 0 and 100.
    Deductions are based on issue severity weights.
    """
    if has_syntax_error:
        return 0, "Critical"

    score = 100
    for issue in issues:
        weight = SEVERITY_WEIGHTS.get(issue.get("severity", "MEDIUM"), 5)
        score -= weight

    score = max(0, min(100, score))

    if score >= 90:
        rating = "Excellent"
    elif score >= 75:
        rating = "Good"
    elif score >= 50:
        rating = "Fair"
    else:
        rating = "Needs Work"

    return score, rating


def _extract_source_line(code, line_number):
    """Safely extract a single source line from code by 1-based index."""
    if not line_number:
        return None
    lines = code.splitlines()
    if 1 <= line_number <= len(lines):
        return lines[line_number - 1].strip()
    return None


def analyze_code(code, enable_ai=True):
    """
    Perform a complete multi-stage analysis of Python code:
    1. Syntax validation
    2. AST structure analysis
    3. Static bug & code smell detection
    4. Safe runtime execution & exception capture
    5. Issue aggregation, severity classification, and health scoring
    6. Local AI-powered explanation and fix suggestions via Ollama (if enabled)
    """
    result = {
        "syntax": analyze_syntax(code),
        "ast": analyze_ast(code),
        "static": {},
        "runtime": None,
        "ai_analysis": None,
        "issues": [],
        "summary": {
            "total_issues": 0,
            "total_static_issues": 0,
            "critical_issues": 0,
            "high_issues": 0,
            "medium_issues": 0,
            "low_issues": 0,
            "info_issues": 0,
            "health_score": 0,
            "health_rating": "Critical",
            "syntax_status": "Unknown",
            "runtime_status": "Not Run",
            "ai_status": "Not Run",
        },
    }

    # Handle syntax error: stop deeper execution
    if result["syntax"]["has_error"]:
        syntax_info = result["syntax"]
        explanation = get_explanation("syntax_error")
        issue = {
            "id": "issue-syntax-1",
            "category": "Syntax",
            "severity": "CRITICAL",
            "message": syntax_info.get("message", "Syntax error in code."),
            "line": syntax_info.get("line"),
            "column": syntax_info.get("column"),
            "source_line": _extract_source_line(code, syntax_info.get("line")),
            "explanation": explanation,
            "suggested_fix": "Fix the syntax error at the indicated position.",
        }
        result["issues"].append(issue)
        result["summary"]["total_issues"] = 1
        result["summary"]["critical_issues"] = 1
        result["summary"]["health_score"] = 0
        result["summary"]["health_rating"] = "Critical"
        result["summary"]["syntax_status"] = "Error"
        result["summary"]["runtime_status"] = "Skipped"

        # AI analysis can still provide fix for syntax error if requested
        if enable_ai and code and code.strip():
            result["ai_analysis"] = analyze_with_ai(
                code,
                [{"category": "Syntax", "severity": "CRITICAL", "message": syntax_info.get("message"), "line": syntax_info.get("line")}],
            )
            result["summary"]["ai_status"] = "Completed" if (result["ai_analysis"] and result["ai_analysis"].get("success")) else "Unavailable"
        return result

    result["summary"]["syntax_status"] = "Passed"

    # Static analysis detectors
    static_results = {
        "unused_variables": find_unused_variables(code),
        "unused_imports": find_unused_imports(code),
        "mutable_defaults": find_mutable_defaults(code),
        "bare_except": find_bare_except(code),
        "broad_except": find_broad_except(code),
        "undefined_variables": find_undefined_variables(code),
        "dangerous_eval": find_dangerous_eval(code),
        "dangerous_exec": find_dangerous_exec(code),
        "division_by_zero": find_division_by_zero(code),
        "unreachable_code": find_unreachable_code(code),
        "none_comparison": find_none_comparison(code),
        "debug_prints": find_debug_prints(code),
        "suspicious_conditions": find_suspicious_conditions(code),
        "shadowed_builtins": find_shadowed_builtins(code),
    }

    # Populate result["static"] for backward compatibility
    for issue_type, findings in static_results.items():
        result["static"][issue_type] = {
            "findings": findings,
            "explanation": get_explanation(issue_type),
        }

    total_static_issues = sum(
        len(issue["findings"])
        for issue in result["static"].values()
    )
    result["summary"]["total_static_issues"] = total_static_issues

    # Build unified structured issues list from static checks
    issue_counter = 1

    # Unused variables
    for var in static_results["unused_variables"]:
        exp = get_explanation("unused_variables")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Code Quality"),
            "severity": exp.get("severity", "MEDIUM"),
            "message": f"Variable '{var}' is assigned a value but is never used.",
            "line": None,
            "source_line": None,
            "explanation": exp,
            "suggested_fix": f"Remove '{var}' or use it in subsequent calculations.",
        })
        issue_counter += 1

    # Unused imports
    for imp in static_results["unused_imports"]:
        exp = get_explanation("unused_imports")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Code Quality"),
            "severity": exp.get("severity", "LOW"),
            "message": f"Imported module/name '{imp}' is never referenced in this code.",
            "line": None,
            "source_line": None,
            "explanation": exp,
            "suggested_fix": f"Remove 'import {imp}' if it is not required.",
        })
        issue_counter += 1

    # Mutable defaults
    for item in static_results["mutable_defaults"]:
        exp = get_explanation("mutable_defaults")
        line = item.get("line")
        fn = item.get("function")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Bug Risk"),
            "severity": exp.get("severity", "HIGH"),
            "message": f"Function '{fn}' defines a mutable default argument (retained across calls).",
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": "Change default value to None and initialize mutable collection inside function body.",
        })
        issue_counter += 1

    # Bare except
    for item in static_results["bare_except"]:
        exp = get_explanation("bare_except")
        line = item.get("line")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Exception Handling"),
            "severity": exp.get("severity", "HIGH"),
            "message": "Bare 'except:' caught all exceptions unconditionally, masking critical errors.",
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": "Specify a concrete exception type like 'except ValueError:' or 'except Exception:'.",
        })
        issue_counter += 1

    # Broad except
    for item in static_results["broad_except"]:
        exp = get_explanation("broad_except")
        line = item.get("line")
        ex_type = item.get("type", "Exception")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Exception Handling"),
            "severity": exp.get("severity", "MEDIUM"),
            "message": f"Broad except handler for '{ex_type}' silently ignores errors with 'pass'.",
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": "Log the error, handle specific exceptions, or avoid empty pass blocks.",
        })
        issue_counter += 1

    # Undefined variables
    for var in static_results["undefined_variables"]:
        exp = get_explanation("undefined_variables")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Name Resolution"),
            "severity": exp.get("severity", "CRITICAL"),
            "message": f"Variable or identifier '{var}' is accessed before assignment.",
            "line": None,
            "source_line": None,
            "explanation": exp,
            "suggested_fix": f"Assign a value to '{var}' before accessing it, or verify spelling.",
        })
        issue_counter += 1

    # Dangerous eval
    for item in static_results["dangerous_eval"]:
        exp = get_explanation("dangerous_eval")
        line = item.get("line")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Security"),
            "severity": exp.get("severity", "CRITICAL"),
            "message": "Dangerous call to eval() can lead to arbitrary code execution.",
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": "Use ast.literal_eval() for data structures or standard Python constructs.",
        })
        issue_counter += 1

    # Dangerous exec
    for item in static_results["dangerous_exec"]:
        exp = get_explanation("dangerous_exec")
        line = item.get("line")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Security"),
            "severity": exp.get("severity", "CRITICAL"),
            "message": "Dangerous call to exec() can dynamically execute malicious code statements.",
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": "Avoid exec() and refactor with standard functions or dictionary mappings.",
        })
        issue_counter += 1

    # Division by zero
    for item in static_results["division_by_zero"]:
        exp = get_explanation("division_by_zero")
        line = item.get("line")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Arithmetic"),
            "severity": exp.get("severity", "HIGH"),
            "message": "Division, floor-division, or modulo operation by literal zero.",
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": "Ensure the denominator is non-zero before dividing.",
        })
        issue_counter += 1

    # Unreachable code
    for item in static_results["unreachable_code"]:
        exp = get_explanation("unreachable_code")
        line = item.get("line")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Dead Code"),
            "severity": exp.get("severity", "LOW"),
            "message": "Statement follows return, raise, break, or continue and will never execute.",
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": "Remove dead code or place it prior to the control jump.",
        })
        issue_counter += 1

    # None comparison
    for item in static_results["none_comparison"]:
        exp = get_explanation("none_comparison")
        line = item.get("line")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Best Practice"),
            "severity": exp.get("severity", "LOW"),
            "message": "Comparison with None using '==' or '!=' instead of identity check.",
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": "Use 'is None' or 'is not None'.",
        })
        issue_counter += 1

    # Debug prints
    for item in static_results["debug_prints"]:
        exp = get_explanation("debug_prints")
        line = item.get("line")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Code Hygiene"),
            "severity": exp.get("severity", "INFO"),
            "message": "print() statement detected in source code.",
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": "Clean up debug prints or configure logging for production code.",
        })
        issue_counter += 1

    # Suspicious conditions
    for item in static_results["suspicious_conditions"]:
        exp = get_explanation("suspicious_conditions")
        line = item.get("line")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Logic Flaw"),
            "severity": exp.get("severity", "MEDIUM"),
            "message": item.get("message", "Suspicious conditional statement detected."),
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": "Review the condition to verify it checks a meaningful dynamic variable.",
        })
        issue_counter += 1

    # Shadowed builtins
    for item in static_results["shadowed_builtins"]:
        exp = get_explanation("shadowed_builtins")
        line = item.get("line")
        var = item.get("variable")
        result["issues"].append({
            "id": f"issue-{issue_counter}",
            "category": exp.get("category", "Naming"),
            "severity": exp.get("severity", "MEDIUM"),
            "message": f"Identifier '{var}' shadows a standard Python built-in.",
            "line": line,
            "source_line": _extract_source_line(code, line),
            "explanation": exp,
            "suggested_fix": f"Rename '{var}' to avoid masking the built-in function or type.",
        })
        issue_counter += 1

    # Run safe runtime execution
    runtime_result = analyze_runtime(code)

    if runtime_result["has_error"]:
        runtime_result["explanation"] = get_explanation(
            runtime_result["issue_type"]
        )
        runtime_exp = runtime_result["explanation"]
        err_sev = "CRITICAL" if runtime_result["issue_type"] == "name_error" else runtime_exp.get("severity", "HIGH")

        # Format exception message accurately without 'None'
        exc_msg = runtime_result.get("exception_message")
        if exc_msg and exc_msg != runtime_result["error_type"]:
            display_msg = f"{runtime_result['error_type']}: {exc_msg}"
        else:
            display_msg = runtime_result["error_type"]

        runtime_issue = {
            "id": f"issue-{issue_counter}",
            "category": runtime_exp.get("category", "Runtime Error"),
            "severity": err_sev,
            "message": display_msg,
            "line": runtime_result.get("line_number"),
            "source_line": runtime_result.get("source_line"),
            "explanation": runtime_exp,
            "suggested_fix": runtime_exp.get("suggestion", "Resolve the exception condition in the code."),
        }
        result["issues"].append(runtime_issue)
        issue_counter += 1
        result["summary"]["runtime_status"] = runtime_result["error_type"]
    else:
        runtime_result["explanation"] = None
        result["summary"]["runtime_status"] = "Passed"

    result["runtime"] = runtime_result

    # Compute summary severity counts
    critical_c = sum(1 for i in result["issues"] if i.get("severity") == "CRITICAL")
    high_c = sum(1 for i in result["issues"] if i.get("severity") == "HIGH")
    med_c = sum(1 for i in result["issues"] if i.get("severity") == "MEDIUM")
    low_c = sum(1 for i in result["issues"] if i.get("severity") == "LOW")
    info_c = sum(1 for i in result["issues"] if i.get("severity") == "INFO")

    health_score, health_rating = _calculate_health_score(result["issues"], False)

    result["summary"]["total_issues"] = len(result["issues"])
    result["summary"]["critical_issues"] = critical_c
    result["summary"]["high_issues"] = high_c
    result["summary"]["medium_issues"] = med_c
    result["summary"]["low_issues"] = low_c
    result["summary"]["info_issues"] = info_c
    result["summary"]["health_score"] = health_score
    result["summary"]["health_rating"] = health_rating

    # Prepare detected issues for AI analysis
    detected_issues = {}

    for issue_type, issue_data in result["static"].items():
        if issue_data["findings"]:
            detected_issues[issue_type] = issue_data["findings"]

    if runtime_result["has_error"]:
        detected_issues["runtime_error"] = {
            "error_type": runtime_result["error_type"],
            "exception_message": runtime_result.get("exception_message", ""),
            "line_number": runtime_result["line_number"],
            "source_line": runtime_result["source_line"],
        }

    # Trigger AI analysis if enabled and issues exist
    if enable_ai and detected_issues:
        result["ai_analysis"] = analyze_with_ai(code, detected_issues)
        if result["ai_analysis"] and result["ai_analysis"].get("success"):
            result["summary"]["ai_status"] = "Completed"
        else:
            result["summary"]["ai_status"] = "Unavailable"
    elif not enable_ai:
        result["summary"]["ai_status"] = "Disabled"
    else:
        result["summary"]["ai_status"] = "No Issues"

    return result