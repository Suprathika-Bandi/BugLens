# BugLens 🔍
### Intelligent Python Bug Detection and Explanation Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-lightgrey.svg)](https://flask.palletsprojects.com/)
[![Ollama](https://img.shields.io/badge/AI-Ollama%20(llama3.2)-purple.svg)](https://ollama.com/)
[![Tests](https://img.shields.io/badge/Tests-80%20Passing-brightgreen.svg)](https://pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)

**BugLens** is a developer-centric web application that detects, classifies, explains, and fixes Python bugs before they impact production. It combines deep AST inspection, deterministic static analysis, sandboxed runtime execution, and local AI (via Ollama) into a unified, developer-dashboard experience.

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation (Windows & Cross-Platform)](#-installation)
- [Ollama Setup (llama3.2)](#-ollama-setup-llama32)
- [Running BugLens](#-running-buglens)
- [How AI Analysis Works](#-how-ai-analysis-works)
- [Static Bug Categories & Severity](#-static-bug-categories--severity)
- [Code Health Scoring Model](#-code-health-scoring-model)
- [Screenshots & UI Showcase](#-screenshots--ui-showcase)
- [Running the Test Suite](#-running-the-test-suite)
- [API Reference](#-api-reference)
- [Troubleshooting](#-troubleshooting)
- [Future Enhancements](#-future-enhancements)
- [License](#-license)

---

## 📌 Overview

Traditional debugging typically requires switching between linters, manual traceback reading, and ad-hoc searches. **BugLens** unifies the entire debugging pipeline:

1. **Syntax Checking**: Instant syntax error localization down to line and column.
2. **AST Deep Inspection**: Parse-tree symbol mapping (functions, classes, imports, variable scopes).
3. **Static Bug Detection**: 14+ rules detecting code smells, anti-patterns, and security hazards.
4. **Runtime Sandbox**: Safe execution in an isolated subprocess with timeout guarantees.
5. **Severity Classification**: Clear `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, and `INFO` grading.
6. **Code Health Score**: Dynamic `0–100` health score reflecting overall code quality.
7. **Local AI Analysis**: Offline, privacy-first explanations and corrected code via local Ollama (`llama3.2`).

---

## 🚀 Key Features

- **⚡ Instant Multi-Layer Analysis**: Detects compile-time syntax errors, static code smells, and runtime exceptions in one run.
- **🛡️ Sandboxed Runtime Execution**: Subprocess isolation with strict 5-second timeouts protects against infinite loops and server hangs.
- **🤖 100% Local AI Integration**: Uses Ollama with `llama3.2` locally. No API keys, no subscriptions, and zero code sent to external cloud APIs.
- **📊 Code Health Rating**: Mathematically calculates an objective quality score (`0-100`) with rating tiers (*Excellent*, *Good*, *Fair*, *Needs Work*, *Critical*).
- **🎨 Modern Dark Developer UI**: Designed with clean typography, synchronized line numbers, code presets, copy-to-clipboard actions, and keyboard shortcuts (`Ctrl + Enter`).
- **📱 Fully Responsive**: 2-column layout on desktop smoothly collapses into an organized stacked view on tablets and mobile devices.
- **🔌 REST API Endpoint**: `/api/analyze` and `/api/status` endpoints support programmatic integration.

---

## 🏗️ Architecture

```text
                     ┌────────────────────────────────────────┐
                     │          Browser / Developer           │
                     └───────────────────┬────────────────────┘
                                         │
                         HTTP / REST API │ (JSON / Form POST)
                                         ▼
                     ┌────────────────────────────────────────┐
                     │           Flask Application            │
                     │          (app.py / REST API)           │
                     └───────────────────┬────────────────────┘
                                         │
                                         ▼
                     ┌────────────────────────────────────────┐
                     │       BugLens Coordinator Engine       │
                     │       (analyzers/bug_analyzer.py)      │
                     └───────┬───────────┬────────────┬───────┘
                             │           │            │
       ┌─────────────────────┘           │            └─────────────────────┐
       ▼                                 ▼                                  ▼
┌──────────────┐               ┌──────────────────┐               ┌──────────────────┐
│    Syntax    │               │   Static / AST   │               │ Runtime Sandbox  │
│   Analyzer   │               │    Analyzers     │               │ (subprocess run) │
└──────┬───────┘               └─────────┬────────┘               └─────────┬────────┘
       │                                 │                                  │
       └─────────────────────────┬───────┴──────────────────────────────────┘
                                 │
                                 ▼
                     ┌────────────────────────────────────────┐
                     │        Explanation & Severity          │
                     │  (CRITICAL, HIGH, MEDIUM, LOW, INFO)   │
                     └───────────────────┬────────────────────┘
                                         │
                                         ▼
                     ┌────────────────────────────────────────┐
                     │       Local Ollama AI Integration      │
                     │        (http://localhost:11434)        │
                     │        Default Model: llama3.2         │
                     └───────────────────┬────────────────────┘
                                         │
                                         ▼
                     ┌────────────────────────────────────────┐
                     │       Developer Results Dashboard      │
                     │   Health Score • Issues • AI Fixes     │
                     └────────────────────────────────────────┘
```

---

## 💻 Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **Backend** | Python 3.10+, Flask 3.x | Lightweight, modular WSGI architecture |
| **Static Analysis** | Python `ast`, `builtins` | Abstract Syntax Tree traversal & scoping |
| **Runtime Engine** | Python `subprocess` | Sandboxed subprocess with 5s timeout & stderr capture |
| **AI Inference** | Ollama HTTP API | Local inference, zero external dependencies |
| **Default AI Model** | `llama3.2:latest` | Configurable via `OLLAMA_MODEL` environment variable. Cold-start ~24 s, warm ~2-4 s. |
| **Frontend** | HTML5, CSS3, Modern JS | Dark theme, CSS variables, responsive grid, zero heavy UI frameworks |
| **Test Suite** | Pytest 8.x+ | 79 unit and integration test cases |

---

## 📂 Project Structure

```text
BugLens/
├── analyzers/
│   ├── __init__.py               # Analyzer package initialization
│   ├── ai_analyzer.py            # Robust Ollama HTTP integration & JSON parser
│   ├── ast_analyzer.py           # AST metric extraction (classes, functions, imports)
│   ├── bug_analyzer.py           # Main coordinator & health score calculator
│   ├── explanation_engine.py     # Rule-based explanations & severity database
│   ├── runtime_analyzer.py       # Sandboxed subprocess runner with timeout guards
│   ├── static_analyzer.py        # 14+ static detectors (mutable defaults, dead code, etc.)
│   └── syntax_analyzer.py        # Python AST grammar & syntax validator
├── static/
│   ├── script.js                 # Line numbers, editor tab handling, presets, clipboard
│   └── style.css                 # Dark developer dashboard styles & responsive layout
├── templates/
│   └── index.html                # Semantic, accessible developer dashboard UI
├── tests/
│   ├── test_ai_analyzer.py       # Ollama integration, parsing, fallback tests
│   ├── test_app.py               # Flask endpoints & HTML rendering tests
│   ├── test_ast.py               # AST visitor and token tests
│   ├── test_bug_analyzer.py      # End-to-end bug detection pipeline tests
│   ├── test_enhanced.py          # Static rules, health scoring, API, & exception tests
│   ├── test_explanation.py       # Explanation catalog & severity tests
│   ├── test_runtime.py           # Runtime sandbox & timeout execution tests
│   ├── test_static.py            # Static analysis rule tests
│   └── test_syntax.py            # Syntax validator tests
├── app.py                        # Flask server, route controllers, and REST APIs
├── pytest.ini                    # Pytest configuration with pythonpath
├── requirements.txt              # Minimal project dependencies
└── README.md                     # Comprehensive project documentation
```

---

## ⚙️ Prerequisites

1. **Python 3.10+** (Tested on Python 3.14 on Windows)
2. **Git**
3. **Ollama** (for local AI features)
   - Download from [ollama.com/download](https://ollama.com/download)

---

## 📦 Installation (Windows & Cross-Platform)

### 1. Clone the repository
```powershell
git clone https://github.com/Nitheesha-Gundloor/BugLens.git
cd BugLens
```

### 2. Create and activate a Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

---

## 🦙 Ollama Setup (`llama3.2`)

BugLens uses **Ollama** locally for AI analysis.

### 1. Start Ollama
Ensure Ollama is running in your background or terminal:
```powershell
ollama serve
```

### 2. Download the Default Model (`llama3.2`)
```powershell
ollama pull llama3.2
```

### 3. Optional Environment Overrides
You can customize the model or endpoint using environment variables:
```powershell
# Custom model
$env:OLLAMA_MODEL="llama3.2"

# Custom endpoint (if running on a LAN machine or custom port)
$env:OLLAMA_URL="http://localhost:11434/api/generate"
```

> **Note:** If Ollama is offline or the model is not installed, BugLens will **never crash**. It will display full rule-based analysis and explain how to start Ollama.

---

## ▶️ Running BugLens

1. Make sure your virtual environment is active:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
2. Start the application:
   ```powershell
   python app.py
   ```
3. Open your browser and navigate to:
   ```text
   http://127.0.0.1:5000
   ```

---

## 🧠 How AI Analysis Works

When you analyze Python code with the AI toggle enabled:
1. BugLens runs static and runtime analysis to collect deterministic bug data.
2. The code and findings are passed to your local Ollama HTTP endpoint (`/api/generate`).
3. BugLens requests a structured JSON schema:
   ```json
   {
       "explanation": "Clear explanation of the detected problems.",
       "why_it_happens": "Root cause of why the error occurs in Python.",
       "suggested_fix": "Step-by-step instructions to fix the issue.",
       "corrected_code": "Complete working corrected Python code.",
       "changes_made": ["Change 1", "Change 2"]
   }
   ```
4. BugLens parses the response, renders the explanation, and provides a **"Copy Code"** button for the suggested fix.

---

## 🛡️ Static Bug Categories & Severity

| Detector | Category | Severity | Description |
|---|---|---|---|
| `syntax_error` | Syntax | **CRITICAL** | Code fails to parse into Python AST |
| `undefined_variables` | Name Resolution | **CRITICAL** | Accessing variables prior to assignment |
| `dangerous_eval` | Security | **CRITICAL** | `eval()` execution of dynamic expressions |
| `dangerous_exec` | Security | **CRITICAL** | `exec()` execution of arbitrary code statements |
| `mutable_defaults` | Bug Risk | **HIGH** | Function arguments using `[]`, `{}`, or `set()` as defaults |
| `bare_except` | Exception Handling | **HIGH** | `except:` catching system signals like KeyboardInterrupt |
| `division_by_zero` | Arithmetic | **HIGH** | Literal division or modulo by `0` |
| `zero_division_error` | Runtime Error | **HIGH** | Runtime division by zero |
| `suspicious_conditions`| Logic Flaw | **MEDIUM** | `x == x` or constant condition `if True:` |
| `shadowed_builtins` | Naming | **MEDIUM** | Overwriting builtins like `list`, `dict`, `str`, `sum` |
| `broad_except` | Exception Handling | **MEDIUM** | Catching broad `Exception` with silent `pass` |
| `unused_variables` | Code Quality | **MEDIUM** | Assigned variable never referenced |
| `unreachable_code` | Dead Code | **LOW** | Statements following `return`, `raise`, or `break` |
| `none_comparison` | Best Practice | **LOW** | `x == None` instead of `x is None` |
| `unused_imports` | Code Quality | **LOW** | Imported module never used |
| `debug_prints` | Code Hygiene | **INFO** | Leftover `print()` statements |

---

## 💯 Code Health Scoring Model

BugLens calculates a real-time Code Health Score between **0 and 100**:

$$\text{Health Score} = \max\left(0, 100 - \sum \text{Severity Weights}\right)$$

- **Syntax Error**: Immediate score of `0` (*Critical*)
- **CRITICAL Issue**: `-25 pts`
- **HIGH Issue**: `-15 pts`
- **MEDIUM Issue**: `-8 pts`
- **LOW Issue**: `-3 pts`
- **INFO Issue**: `-1 pt`

| Score Range | Rating Tier | Badge Color |
|---|---|---|
| 90 – 100 | **Excellent** | Green |
| 75 – 89 | **Good** | Cyan / Blue |
| 50 – 74 | **Fair** | Amber / Orange |
| 0 – 49 | **Needs Work / Critical** | Red |

---

## 📸 Screenshots & UI Showcase

*(Place screenshots here)*

### 1. Developer Dashboard & Code Editor
> Clean dark theme, synchronized line numbers, example presets dropdown, and keyboard shortcuts.

### 2. Multi-Stage Bug Report
> Issue cards grouped by severity with source code line previews, descriptions, and recommended fixes.

### 3. Local AI Analysis with llama3.2
> AI explanation, root cause analysis, and one-click copyable corrected code.

---

## 🧪 Running the Test Suite

BugLens maintains a 100% green test suite with **80 comprehensive unit and integration tests**.

Run all tests via Pytest:
```powershell
python -m pytest
```

Run with verbose test reporting:
```powershell
python -m pytest -v
```

Expected output:
```text
============================= 80 passed in 11.xx s =============================
```

> **Note on AI timing:** The first analysis after starting Ollama may take ~24 seconds (cold model load from disk). Subsequent analyses complete in ~2–4 seconds. BugLens displays deterministic results immediately and loads AI results in the background.

---

## 🔌 API Reference

### 1. `POST /api/analyze`
Analyze Python code asynchronously.

**Request:**
```http
POST /api/analyze HTTP/1.1
Content-Type: application/json

{
    "code": "def divide(a, b):\n    return a / b\nprint(divide(10, 0))",
    "enable_ai": false
}
```

**Response:**
```json
{
    "success": true,
    "result": {
        "summary": {
            "health_score": 85,
            "health_rating": "Good",
            "total_issues": 1,
            "critical_issues": 0,
            "high_issues": 1,
            "medium_issues": 0,
            "low_issues": 0,
            "info_issues": 0,
            "syntax_status": "Passed",
            "runtime_status": "ZeroDivisionError",
            "ai_status": "Disabled"
        },
        "issues": [...],
        "runtime": {...}
    }
}
```

### 2. `GET /api/status`
Check application and Ollama connectivity status.

**Response:**
```json
{
    "app": "BugLens",
    "status": "healthy",
    "version": "2.0.0",
    "ollama": {
        "online": true,
        "endpoint": "http://localhost:11434/api/generate",
        "target_model": "llama3.2",
        "target_model_installed": true,
        "available_models": ["llama3.2:latest"]
    }
}
```

---

## ❓ Troubleshooting

### 1. `ModuleNotFoundError: No module named 'analyzers'`
Make sure you run tests from the root `BugLens` directory or run with `python -m pytest`. `pytest.ini` automatically sets `pythonpath = .`.

### 2. "Ollama is not running" in AI section
- Verify Ollama is running:
  ```powershell
  curl.exe http://localhost:11434/api/tags
  ```
- If not running, open a new terminal and run:
  ```powershell
  ollama serve
  ```

### 3. "Ollama model 'llama3.2' was not found"
Download the model with:
```powershell
ollama pull llama3.2
```

---

## 🔮 Future Enhancements

- [ ] AST-based automatic refactoring diff view (side-by-side)
- [ ] Exportable PDF / Markdown analysis audit reports
- [ ] Custom user rule configuration (.buglensrc)
- [ ] Multi-file and repository scanning
- [ ] Type annotation inference and checking

---

## 📄 License

This project is licensed under the MIT License — see the repository for details.