/**
 * BugLens 2.0 - Client-Side Interactive Engine
 * Handles fast asynchronous deterministic analysis + non-blocking background AI generation,
 * synchronized line numbers, code editor tabs, preset snippets, and clipboard operations.
 */

// Preset code examples for demo & evaluation
const CODE_EXAMPLES = {
    runtime_zero_division: `# Example 1: Runtime ZeroDivisionError & Unused Variables
import os
import math

def calculate_average(total, count):
    # Bug: Potential division by zero if count is 0
    result = total / count
    return result

total_score = 100
student_count = 0
unused_metric = 42

print("Starting calculation...")
print(calculate_average(total_score, student_count))
`,

    mutable_defaults: `# Example 2: Dangerous Mutable Defaults & Bare Except
def add_to_inventory(item, inventory=[]):
    # Bug: Mutable default list is shared across calls
    inventory.append(item)
    return inventory

order1 = add_to_inventory("Laptop")
order2 = add_to_inventory("Mouse")
print("Inventory:", order2)

try:
    data = int("not_a_number")
except:
    # Bug: Bare except masks all system exceptions
    pass
`,

    none_and_undefined: `# Example 3: None Comparison & NameError
def check_status(user_role):
    # Bug: None compared with == instead of is
    if user_role == None:
        print("Guest user")
    else:
        print("Active user:", user_role)

check_status(None)

# Bug: Undefined variable at runtime
print(z)
`,

    eval_and_shadowing: `# Example 4: Dangerous eval() & Shadowed Builtin
import math

# Bug: Shadowing Python built-in 'list' and 'sum'
list = [10, 20, 30]
sum = 60

user_expr = "10 + 20 * 2"
# Bug: eval() can execute arbitrary malicious code
parsed_value = eval(user_expr)
print("Evaluated:", parsed_value)

# Bug: Suspicious self-comparison
if sum == sum:
    print("Logic check passed")
`,

    clean_code: `# Example 5: Clean Python Code (100% Score)
def add_numbers(a, b):
    """Add two numbers and return the sum."""
    return a + b

result = add_numbers(10, 20)
`
};

document.addEventListener("DOMContentLoaded", () => {
    initCodeEditor();
    initExamples();
    checkOllamaStatus();
    initKeyboardShortcuts();
    initCopyButtons();
    initFormInterception();
});

/**
 * Initialize code editor events, line numbers, and tab indentation
 */
function initCodeEditor() {
    const textarea = document.getElementById("code");
    const lineNumbers = document.getElementById("line-numbers");

    if (!textarea || !lineNumbers) return;

    textarea.addEventListener("input", () => {
        updateLineNumbers();
        updateEditorMetrics();
    });

    textarea.addEventListener("scroll", syncLineNumbers);

    // Support Tab key indentation (4 spaces)
    textarea.addEventListener("keydown", (e) => {
        if (e.key === "Tab") {
            e.preventDefault();
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;

            textarea.value = textarea.value.substring(0, start) + "    " + textarea.value.substring(end);
            textarea.selectionStart = textarea.selectionEnd = start + 4;
            updateLineNumbers();
            updateEditorMetrics();
        }
    });

    updateLineNumbers();
    updateEditorMetrics();
}

function updateLineNumbers() {
    const textarea = document.getElementById("code");
    const lineNumbers = document.getElementById("line-numbers");
    if (!textarea || !lineNumbers) return;

    const lines = textarea.value.split("\n").length;
    let html = "";
    for (let i = 1; i <= lines; i++) {
        html += `<span>${i}</span>`;
    }
    lineNumbers.innerHTML = html;
}

function syncLineNumbers() {
    const textarea = document.getElementById("code");
    const lineNumbers = document.getElementById("line-numbers");
    if (!textarea || !lineNumbers) return;
    lineNumbers.scrollTop = textarea.scrollTop;
}

function updateEditorMetrics() {
    const textarea = document.getElementById("code");
    const charCount = document.getElementById("char-count");
    const lineCount = document.getElementById("line-count");
    if (!textarea) return;

    const text = textarea.value;
    const lines = text ? text.split("\n").length : 0;
    const chars = text.length;

    if (charCount) charCount.textContent = `${chars} chars`;
    if (lineCount) lineCount.textContent = `${lines} lines`;
}

/**
 * Handle Example presets dropdown
 */
function initExamples() {
    const select = document.getElementById("example-select");
    if (!select) return;

    select.addEventListener("change", (e) => {
        const key = e.target.value;
        if (key && CODE_EXAMPLES[key]) {
            loadCode(CODE_EXAMPLES[key]);
            select.value = "";
        }
    });
}

function loadCode(codeString) {
    const textarea = document.getElementById("code");
    if (!textarea) return;
    textarea.value = codeString;
    updateLineNumbers();
    updateEditorMetrics();
    showToast("Example code loaded.");
}

function clearCode() {
    const textarea = document.getElementById("code");
    if (!textarea) return;
    textarea.value = "";
    updateLineNumbers();
    updateEditorMetrics();
    textarea.focus();
    showToast("Editor cleared.");
}

function copySourceCode() {
    const textarea = document.getElementById("code");
    if (!textarea || !textarea.value) {
        showToast("Editor is empty.");
        return;
    }
    navigator.clipboard.writeText(textarea.value).then(() => {
        showToast("Source code copied to clipboard!");
    }).catch(() => {
        showToast("Failed to copy code.");
    });
}

function copyText(text, btnElement) {
    navigator.clipboard.writeText(text).then(() => {
        if (btnElement) {
            const original = btnElement.innerHTML;
            btnElement.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!`;
            setTimeout(() => {
                btnElement.innerHTML = original;
            }, 2000);
        }
        showToast("Copied to clipboard!");
    }).catch(() => {
        showToast("Failed to copy.");
    });
}

function initCopyButtons() {
    document.querySelectorAll(".copy-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-target");
            if (targetId) {
                const target = document.getElementById(targetId);
                if (target) {
                    copyText(target.innerText || target.textContent, btn);
                }
            }
        });
    });
}

/**
 * Check Ollama connection and model status
 */
function checkOllamaStatus() {
    const badge = document.getElementById("ollama-status-badge");
    const statusText = document.getElementById("ollama-status-text");

    fetch("/api/status")
        .then(res => res.json())
        .then(data => {
            if (data.ollama) {
                const o = data.ollama;
                const model = o.target_model || "llama3.2";

                if (badge) {
                    badge.classList.remove("status-online", "status-warning", "status-offline");
                }

                if (o.generation_status === "ready") {
                    if (badge) badge.classList.add("status-online");
                    if (statusText) {
                        statusText.textContent = `Ollama: ${model} (Ready)`;
                        statusText.title = `Connected to Ollama. Model ${model} is installed and ready.`;
                    }
                } else if (o.generation_status === "model_not_found") {
                    if (badge) badge.classList.add("status-warning");
                    if (statusText) {
                        statusText.textContent = `Ollama: ${model} (Missing)`;
                        statusText.title = `Ollama is running, but model '${model}' is not pulled. Run: ollama pull ${model}`;
                    }
                } else {
                    if (badge) badge.classList.add("status-offline");
                    if (statusText) {
                        statusText.textContent = "Ollama: Offline";
                        statusText.title = "Ollama service not detected at http://localhost:11434. Start with: ollama serve";
                    }
                }
            }
        })
        .catch(() => {
            if (badge) {
                badge.classList.remove("status-online", "status-warning");
                badge.classList.add("status-offline");
            }
            if (statusText) statusText.textContent = "Ollama: Offline";
        });
}

/**
 * Keyboard shortcut: Ctrl + Enter to run analysis
 */
function initKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            runInteractiveAnalysis();
        }
    });
}

function initFormInterception() {
    const form = document.getElementById("analyze-form");
    if (form) {
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            runInteractiveAnalysis();
        });
    }
}

/**
 * CORE NON-BLOCKING ANALYSIS WORKFLOW:
 * 1. Runs deterministic analysis immediately via /api/analyze (< 100ms).
 * 2. Displays syntax, AST, static issues, runtime traceback, and health score instantly.
 * 3. Shows "AI is analyzing your code with llama3.2..." in the AI section.
 * 4. Calls /api/analyze-ai in the background, updating the AI section when done.
 * Result: User NEVER waits 90s, nor are deterministic results delayed!
 */
function runInteractiveAnalysis() {
    const textarea = document.getElementById("code");
    if (!textarea || !textarea.value.trim()) {
        showToast("Please enter Python code to analyze.");
        return;
    }

    const code = textarea.value;
    const enableAiCheckbox = document.getElementById("enable_ai");
    const isAiEnabled = enableAiCheckbox ? enableAiCheckbox.checked : true;
    const button = document.getElementById("analyze-btn");

    if (button) {
        button.disabled = true;
        button.innerHTML = `<span class="spinner-small"></span> Analyzing...`;
    }

    // Step 1: Run fast deterministic analysis
    fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code, enable_ai: false })
    })
        .then(res => res.json())
        .then(data => {
            if (button) {
                button.disabled = false;
                button.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Analyze Code <span class="shortcut-hint">Ctrl+↵</span>`;
            }

            if (!data.success || !data.result) {
                showToast(data.error || "Analysis failed.");
                return;
            }

            const result = data.result;

            // Step 2: Render deterministic dashboard immediately
            renderDashboard(result, isAiEnabled);

            // Step 3: Trigger asynchronous AI generation in background if enabled
            if (isAiEnabled) {
                runBackgroundAiAnalysis(code, result.issues || []);
            }
        })
        .catch(err => {
            if (button) {
                button.disabled = false;
                button.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Analyze Code <span class="shortcut-hint">Ctrl+↵</span>`;
            }
            showToast("Error connecting to BugLens backend.");
            console.error(err);
        });
}

/**
 * Asynchronously call /api/analyze-ai in background without blocking the UI
 */
function runBackgroundAiAnalysis(code, detectedIssues) {
    const aiContainer = document.getElementById("ai-analysis-container");
    if (!aiContainer) return;

    fetch("/api/analyze-ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code, detected_issues: detectedIssues })
    })
        .then(res => res.json())
        .then(data => {
            const ai = data.ai_analysis;
            if (data.success && ai && ai.success) {
                renderAiSuccess(ai);
            } else {
                const errorMsg = (ai && ai.error) || data.error || "AI generation failed or timed out.";
                renderAiFailure(errorMsg);
            }
        })
        .catch(err => {
            renderAiFailure("Could not reach local Ollama AI endpoint.");
            console.error(err);
        });
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * Render deterministic analysis results into DOM
 */
function renderDashboard(result, isAiEnabled) {
    const container = document.querySelector(".results-container");
    if (!container) return;

    const summary = result.summary || {};
    const score = summary.health_score ?? 100;
    const rating = summary.health_rating || "Good";

    let scoreClass = "score-good";
    let badgeClass = "badge-low";
    if (score >= 90) { scoreClass = "score-excellent"; badgeClass = "badge-success"; }
    else if (score >= 75) { scoreClass = "score-good"; badgeClass = "badge-low"; }
    else if (score >= 50) { scoreClass = "score-fair"; badgeClass = "badge-high"; }
    else { scoreClass = "score-critical"; badgeClass = "badge-critical"; }

    let issuesHtml = "";
    if (result.issues && result.issues.length > 0) {
        issuesHtml = result.issues.map(issue => `
            <div class="issue-item issue-item-${(issue.severity || 'medium').toLowerCase()}" id="${escapeHtml(issue.id)}">
                <div class="issue-top">
                    <div class="issue-tags">
                        <span class="severity-badge badge-${(issue.severity || 'medium').toLowerCase()}">${escapeHtml(issue.severity)}</span>
                        <span class="category-tag">${escapeHtml(issue.category)}</span>
                        ${issue.line ? `<span class="line-tag">Line ${issue.line}</span>` : ""}
                    </div>
                </div>
                <div class="issue-message">${escapeHtml(issue.message)}</div>
                ${issue.source_line ? `<div class="code-snippet-box"><code>${escapeHtml(issue.source_line)}</code></div>` : ""}
                <div class="issue-details-grid">
                    ${issue.explanation && issue.explanation.description ? `
                    <div class="detail-block">
                        <strong>Explanation</strong>
                        <p>${escapeHtml(issue.explanation.description)}</p>
                    </div>` : ""}
                    ${issue.suggested_fix ? `
                    <div class="detail-block">
                        <strong>Suggested Fix</strong>
                        <p>${escapeHtml(issue.suggested_fix)}</p>
                    </div>` : ""}
                </div>
            </div>
        `).join("");
    } else {
        issuesHtml = `<p style="color: var(--success); margin: 0; font-weight: 500;">Great! No significant issues detected.</p>`;
    }

    // Runtime card HTML
    let runtimeHtml = "";
    if (result.runtime) {
        const rt = result.runtime;
        if (rt.has_error) {
            const rtMsg = rt.exception_message ? `${rt.error_type}: ${rt.exception_message}` : rt.error_type;
            runtimeHtml = `
            <div class="result-card">
                <div class="card-header-row">
                    <h3>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
                        4. Runtime Execution
                    </h3>
                    <span class="severity-badge badge-critical">${escapeHtml(rt.error_type)}</span>
                </div>
                <div class="issue-item issue-item-critical">
                    <div class="issue-message">${escapeHtml(rtMsg)}</div>
                    ${rt.line_number ? `<p class="editor-meta">Failed at line ${rt.line_number}</p>` : ""}
                    ${rt.source_line ? `<div class="code-snippet-box"><code>${escapeHtml(rt.source_line)}</code></div>` : ""}
                    ${rt.explanation ? `
                    <div class="issue-details-grid">
                        <div class="detail-block">
                            <strong>Description</strong>
                            <p>${escapeHtml(rt.explanation.description)}</p>
                        </div>
                        <div class="detail-block">
                            <strong>Suggested Fix</strong>
                            <p>${escapeHtml(rt.explanation.suggestion)}</p>
                        </div>
                    </div>` : ""}
                    <details style="margin-top: 0.75rem;">
                        <summary style="font-size: 0.8rem; color: var(--accent); cursor: pointer;">View Full Traceback</summary>
                        <pre class="code-snippet-box" style="margin-top: 0.4rem; white-space: pre-wrap;">${escapeHtml(rt.message)}</pre>
                    </details>
                </div>
                ${rt.output ? `
                <div class="console-output">
                    <div class="console-header">
                        <div class="terminal-dots"><span class="t-dot t-red"></span><span class="t-dot t-yellow"></span><span class="t-dot t-green"></span></div>
                        <span>Program Output (stdout)</span>
                    </div>
                    <pre style="margin: 0; font-family: inherit;">${escapeHtml(rt.output)}</pre>
                </div>` : ""}
            </div>`;
        } else {
            runtimeHtml = `
            <div class="result-card">
                <div class="card-header-row">
                    <h3>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
                        4. Runtime Execution
                    </h3>
                    <span class="severity-badge badge-success">Success</span>
                </div>
                <p class="editor-meta" style="color: var(--success); margin: 0; font-weight: 500;">
                    Code executed successfully without runtime exceptions.
                </p>
                ${rt.output ? `
                <div class="console-output">
                    <div class="console-header">
                        <div class="terminal-dots"><span class="t-dot t-red"></span><span class="t-dot t-yellow"></span><span class="t-dot t-green"></span></div>
                        <span>Program Output (stdout)</span>
                    </div>
                    <pre style="margin: 0; font-family: inherit;">${escapeHtml(rt.output)}</pre>
                </div>` : ""}
            </div>`;
        }
    }

    // AI Section Placeholder
    let aiPlaceholderHtml = "";
    if (isAiEnabled) {
        aiPlaceholderHtml = `
        <div class="result-card ai-card" id="ai-analysis-container">
            <div class="card-header-row">
                <h3>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--ai-purple)" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"></path><path d="M12 2a10 10 0 0 1 10 10h-10V2z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                    5. AI Analysis
                </h3>
                <span class="ai-badge">llama3.2</span>
            </div>
            <div class="ai-loading-box">
                <div class="spinner-small" style="width: 22px; height: 22px; border-width: 2.5px; border-top-color: var(--ai-purple);"></div>
                <div class="ai-loading-content">
                    <strong>AI is analyzing your code with llama3.2...</strong>
                    <p>Generating root-cause explanation and corrected code in background...</p>
                </div>
            </div>
        </div>`;
    }

    container.innerHTML = `
        <!-- 1. Overview Card -->
        <div class="overview-card">
            <div class="overview-header">
                <h2 class="overview-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>
                    Analysis Overview
                </h2>
                <span class="severity-badge ${badgeClass}">${escapeHtml(rating)}</span>
            </div>

            <div class="score-badge-group">
                <div class="score-number-box ${scoreClass}">
                    <div class="score-number">${score}</div>
                    <div class="score-max">/ 100 Health</div>
                </div>

                <div class="score-details">
                    <div class="score-label-row">
                        <span class="score-rating">Code Health Score</span>
                        <span class="editor-meta">${summary.total_issues || 0} detected issue${(summary.total_issues !== 1) ? 's' : ''}</span>
                    </div>
                    <div class="score-bar-bg">
                        <div class="score-bar-fill ${scoreClass}" style="width: ${score}%;"></div>
                    </div>
                </div>
            </div>

            <div class="issue-counts-grid">
                <div class="count-card count-critical"><span class="count-val">${summary.critical_issues || 0}</span><span class="count-label">Critical</span></div>
                <div class="count-card count-high"><span class="count-val">${summary.high_issues || 0}</span><span class="count-label">High</span></div>
                <div class="count-card count-medium"><span class="count-val">${summary.medium_issues || 0}</span><span class="count-label">Medium</span></div>
                <div class="count-card count-low"><span class="count-val">${summary.low_issues || 0}</span><span class="count-label">Low</span></div>
                <div class="count-card count-info"><span class="count-val">${summary.info_issues || 0}</span><span class="count-label">Info</span></div>
            </div>

            <div class="status-indicators-row">
                <div class="status-pill">
                    <strong>Syntax:</strong>
                    ${result.syntax.has_error ? `<span class="count-critical">Syntax Error</span>` : `<span class="count-low">No Errors</span>`}
                </div>
                <div class="status-pill">
                    <strong>Runtime:</strong>
                    ${result.runtime && result.runtime.has_error ? `<span class="count-critical">${escapeHtml(result.runtime.error_type)}</span>` : `<span class="count-low">No Errors</span>`}
                </div>
                <div class="status-pill">
                    <strong>Local AI:</strong>
                    ${isAiEnabled ? `<span style="color: var(--ai-purple); font-weight:600;">Processing...</span>` : `<span class="editor-meta">Disabled</span>`}
                </div>
            </div>
        </div>

        <!-- 2. Syntax Analysis Card -->
        <div class="result-card">
            <div class="card-header-row">
                <h3>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
                    1. Syntax Analysis
                </h3>
                <span class="severity-badge ${result.syntax.has_error ? 'badge-critical' : 'badge-success'}">${result.syntax.has_error ? 'Syntax Error' : 'Passed'}</span>
            </div>
            ${result.syntax.has_error ? `
            <div class="issue-item issue-item-critical">
                <div class="issue-message">${escapeHtml(result.syntax.message)}</div>
                <p class="editor-meta" style="margin: 0.3rem 0;">Line: ${result.syntax.line} | Column: ${result.syntax.column}</p>
            </div>` : `
            <p class="editor-meta" style="color: var(--success); margin: 0; font-weight: 500;">
                No syntax errors found.
            </p>`}
        </div>

        <!-- 3. AST Analysis Card -->
        <div class="result-card">
            <div class="card-header-row">
                <h3>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
                    2. AST Analysis
                </h3>
                <span class="severity-badge ${result.ast.success ? 'badge-success' : 'badge-critical'}">${result.ast.success ? 'Passed' : 'Failed'}</span>
            </div>
            ${result.ast.success ? `
            <p class="editor-meta" style="color: var(--success); margin: 0 0 0.75rem; font-weight: 500;">
                AST analysis completed successfully.
            </p>
            <div class="ast-metrics-grid">
                <div class="ast-stat-box"><div class="ast-stat-val">${result.ast.node_count || 0}</div><div class="ast-stat-label">AST Nodes</div></div>
                <div class="ast-stat-box"><div class="ast-stat-val">${(result.ast.functions || []).length}</div><div class="ast-stat-label">Functions</div></div>
                <div class="ast-stat-box"><div class="ast-stat-val">${(result.ast.classes || []).length}</div><div class="ast-stat-label">Classes</div></div>
                <div class="ast-stat-box"><div class="ast-stat-val">${(result.ast.imports || []).length}</div><div class="ast-stat-label">Imports</div></div>
            </div>` : `
            <p class="count-critical" style="margin: 0;">${escapeHtml(result.ast.message)}</p>`}
        </div>

        <!-- 4. Rule-Based Issues List -->
        <div class="result-card">
            <div class="card-header-row">
                <h3>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    3. Rule-Based Analysis (${(result.issues || []).length})
                </h3>
                <span class="severity-badge ${(result.issues && result.issues.length > 0) ? 'badge-high' : 'badge-success'}">${(result.issues && result.issues.length > 0) ? 'Issues Found' : 'Clean'}</span>
            </div>
            <div class="issues-stack">
                ${issuesHtml}
            </div>
        </div>

        <!-- 5. Runtime Analysis Card -->
        ${runtimeHtml}

        <!-- 6. AI Section -->
        ${aiPlaceholderHtml}
    `;

    initCopyButtons();
}

/**
 * Render successful AI explanation & fix
 */
function renderAiSuccess(ai) {
    const aiContainer = document.getElementById("ai-analysis-container");
    if (!aiContainer) return;

    let changesHtml = "";
    if (ai.changes_made && ai.changes_made.length > 0) {
        changesHtml = `
        <div class="ai-section-box" style="margin-bottom: 0;">
            <h4>📝 Changes Made</h4>
            <ul class="changes-list">
                ${ai.changes_made.map(c => `<li>${escapeHtml(c)}</li>`).join("")}
            </ul>
        </div>`;
    }

    aiContainer.innerHTML = `
        <div class="card-header-row">
            <h3>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--ai-purple)" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"></path><path d="M12 2a10 10 0 0 1 10 10h-10V2z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                5. AI Analysis
            </h3>
            <span class="ai-badge">Ollama: llama3.2</span>
        </div>

        <div class="ai-section-box">
            <h4>🤖 AI Explanation</h4>
            <p>${escapeHtml(ai.explanation)}</p>
        </div>

        ${ai.why_it_happens ? `
        <div class="ai-section-box">
            <h4>💡 Why It Happens</h4>
            <p>${escapeHtml(ai.why_it_happens)}</p>
        </div>` : ""}

        ${ai.suggested_fix ? `
        <div class="ai-section-box">
            <h4>🔧 Suggested Fix</h4>
            <p>${escapeHtml(ai.suggested_fix)}</p>
        </div>` : ""}

        ${ai.corrected_code ? `
        <div class="ai-section-box">
            <div class="code-block-header">
                <span style="font-weight: 600; color: var(--accent);">AI Suggested Fix</span>
                <button type="button" class="btn btn-secondary btn-sm copy-btn" data-target="ai-corrected-code" title="Copy corrected code">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    Copy Code
                </button>
            </div>
            <pre class="code-block"><code id="ai-corrected-code">${escapeHtml(ai.corrected_code)}</code></pre>
        </div>` : ""}

        ${changesHtml}
    `;

    initCopyButtons();
    showToast("AI analysis complete!");
}

/**
 * Render friendly AI failure notice
 */
function renderAiFailure(errorMessage) {
    const aiContainer = document.getElementById("ai-analysis-container");
    if (!aiContainer) return;

    aiContainer.innerHTML = `
        <div class="card-header-row">
            <h3>5. AI Analysis</h3>
            <span class="severity-badge badge-high">AI Notice</span>
        </div>
        <div class="issue-item issue-item-high">
            <div class="issue-message">AI analysis unavailable</div>
            <p class="editor-meta" style="color: var(--text-secondary); margin: 0.4rem 0;">
                ${escapeHtml(errorMessage)}
            </p>
            <p class="editor-meta" style="margin: 0; color: var(--text-muted);">
                Deterministic BugLens analysis is 100% complete above. To enable AI, ensure Ollama is running with <code>ollama pull llama3.2</code>.
            </p>
        </div>
    `;
}

/**
 * Toast notification banner
 */
function showToast(message) {
    let toast = document.getElementById("app-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "app-toast";
        toast.className = "toast";
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add("visible");
    setTimeout(() => {
        toast.classList.remove("visible");
    }, 3000);
}
