import os
import re
import subprocess
import sys
import tempfile

RUNTIME_ERROR_MAPPING = {
    "ZeroDivisionError": "zero_division_error",
    "NameError": "name_error",
    "TypeError": "type_error",
    "IndexError": "index_error",
    "KeyError": "key_error",
    "AttributeError": "attribute_error",
    "ValueError": "value_error",
    "TimeoutError": "timeout_error",
    "RecursionError": "timeout_error",
    "SyntaxError": "syntax_error",
}

EXECUTION_TIMEOUT = 5


def analyze_runtime(code):
    """
    Execute submitted Python code safely within an isolated subprocess,
    capturing stdout, stderr, exceptions, traceback, exception details, and execution line.
    """
    if not code or not code.strip():
        return {
            "has_error": False,
            "error_type": None,
            "issue_type": None,
            "exception_message": "",
            "message": "No code provided for runtime execution.",
            "output": "",
            "line_number": None,
            "source_line": None,
        }

    temp_file = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as file:
            file.write(code)
            temp_file = file.name

        # Run with isolated subprocess and execution timeout
        result = subprocess.run(
            [sys.executable, "-I", temp_file],
            capture_output=True,
            text=True,
            timeout=EXECUTION_TIMEOUT,
        )

        if result.returncode == 0:
            return {
                "has_error": False,
                "error_type": None,
                "issue_type": None,
                "exception_message": "",
                "message": "Code executed successfully.",
                "output": result.stdout,
                "line_number": None,
                "source_line": None,
            }

        error_message = result.stderr.strip()

        # Extract the line number from the traceback (take the last occurrence in user code)
        line_number = None
        line_matches = re.findall(r'File ".*?", line (\d+)', error_message)
        if line_matches:
            line_number = int(line_matches[-1])
        else:
            fallback_match = re.search(r"line (\d+)", error_message)
            if fallback_match:
                line_number = int(fallback_match.group(1))

        # Extract the actual error type and exception message from the last non-empty line
        error_type = "RuntimeError"
        exception_message = ""
        error_lines = [l.strip() for l in error_message.splitlines() if l.strip()]

        if error_lines:
            last_line = error_lines[-1]
            if ":" in last_line:
                parts = last_line.split(":", 1)
                error_type = parts[0].strip()
                exception_message = parts[1].strip()
            else:
                error_type = last_line.strip()
                exception_message = last_line.strip()

        # Map Python error type to BugLens issue type
        issue_type = RUNTIME_ERROR_MAPPING.get(
            error_type,
            "runtime_error",
        )

        # Get the source line that caused the error
        source_line = None
        if line_number is not None:
            code_lines = code.splitlines()
            if 1 <= line_number <= len(code_lines):
                source_line = code_lines[line_number - 1].strip()

        return {
            "has_error": True,
            "error_type": error_type,
            "issue_type": issue_type,
            "exception_message": exception_message,
            "message": error_message,
            "output": result.stdout,
            "line_number": line_number,
            "source_line": source_line,
        }

    except subprocess.TimeoutExpired:
        return {
            "has_error": True,
            "error_type": "TimeoutError",
            "issue_type": "timeout_error",
            "exception_message": f"Execution exceeded the {EXECUTION_TIMEOUT}-second limit",
            "message": f"Code execution exceeded the {EXECUTION_TIMEOUT}-second limit (possible infinite loop).",
            "output": "",
            "line_number": None,
            "source_line": None,
        }

    except Exception as exc:
        return {
            "has_error": True,
            "error_type": "ExecutionError",
            "issue_type": "runtime_error",
            "exception_message": str(exc),
            "message": f"Execution could not be completed: {exc}",
            "output": "",
            "line_number": None,
            "source_line": None,
        }

    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass