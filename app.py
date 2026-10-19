import json
import os
import urllib.request
from flask import Flask, jsonify, render_template, request

from database.db import init_db
from database.db import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
from flask import redirect, url_for, session, flash
import sqlite3
from analyzers.ai_analyzer import analyze_with_ai, get_ollama_model, get_ollama_url
from analyzers.bug_analyzer import analyze_code

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "buglens-secure-dev-key")
with app.app_context():
    init_db()
@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate an existing BugLens user."""

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter your email and password.", "error")
            return render_template("login.html")

        connection = get_db_connection()

        try:
            user = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        finally:
            connection.close()

        if user is None or not check_password_hash(
            user["password_hash"], password
        ):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]

        flash("Login successful! Welcome back.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")
@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Register a new BugLens user."""

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validate submitted fields
        if not name or not email or not password or not confirm_password:
            flash("Please fill in all fields.", "error")
            return render_template("signup.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return render_template("signup.html")

        password_hash = generate_password_hash(password)

        connection = get_db_connection()

        try:
            connection.execute(
                """
                INSERT INTO users (name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (name, email, password_hash),
            )
            connection.commit()

        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "error")
            return render_template("signup.html")

        finally:
            connection.close()

        flash("Your account was created successfully. Please sign in.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/logout", methods=["GET"])
def logout():
    """Log out the current BugLens user."""
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("home"))

@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Display the dashboard to logged-in users."""

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    connection = get_db_connection()

    try:
        total_analyses = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM analysis_history
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()["total"]

        bugs_detected = connection.execute(
            """
            SELECT COALESCE(SUM(bugs_found), 0) AS total
            FROM analysis_history
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()["total"]

        average_health = connection.execute(
            """
            SELECT AVG(health_score) AS average
            FROM analysis_history
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()["average"]
        recent_analyses = connection.execute(
            """
            SELECT id, submitted_code, health_score,
                   bugs_found, created_at
            FROM analysis_history
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 5
            """,
            (user_id,)
        ).fetchall()

    finally:
        connection.close()

    average_health = (
        round(average_health)
        if average_health is not None
        else None
    )

    return render_template(
        "dashboard.html",
        total_analyses=total_analyses,
        bugs_detected=bugs_detected,
        average_health=average_health,
        recent_analyses=recent_analyses
    )
@app.route("/history", methods=["GET"])
def analysis_history():
    """Display filtered analysis history for the logged-in user."""

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # Read the selected history filter.
    filter_type = request.args.get("filter", "all")
    print("DEBUG: Selected history filter =", filter_type)

    connection = get_db_connection()

    try:
        if filter_type == "bugs":
            print("DEBUG: Running filter =", filter_type)
            analyses = connection.execute(
                """
                SELECT
                    id,
                    submitted_code,
                    analysis_result,
                    health_score,
                    bugs_found,
                    created_at
                FROM analysis_history
                WHERE user_id = ?
                  AND bugs_found > 0
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()

        elif filter_type == "health":
            print("DEBUG: Running filter =", filter_type)
            analyses = connection.execute(
                """
                SELECT
                    id,
                    submitted_code,
                    analysis_result,
                    health_score,
                    bugs_found,
                    created_at
                FROM analysis_history
                WHERE user_id = ?
                ORDER BY health_score ASC, created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()

        else:
            # Show all analyses.
            filter_type = "all"
            print("DEBUG: Running filter =", filter_type)

            analyses = connection.execute(
                """
                SELECT
                    id,
                    submitted_code,
                    analysis_result,
                    health_score,
                    bugs_found,
                    created_at
                FROM analysis_history
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()

    finally:
        connection.close()

    return render_template(
        "history.html",
        analyses=analyses,
        filter_type=filter_type,
    )
@app.route("/", methods=["GET"])
def home():
    """Display the BugLens landing page."""

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("home.html")


@app.route("/analyzer", methods=["GET", "POST"])
def analyzer():
    """Display the code analyzer and process submitted Python code."""

    if "user_id" not in session:
        return redirect(url_for("login"))

    result = None
    code = ""
    enable_ai = True

    if request.method == "POST":
        code = request.form.get("code", "")

        enable_ai = request.form.get(
            "enable_ai", "true"
        ).lower() in ("true", "1", "on", "yes")

        if code.strip():
            result = analyze_code(code, enable_ai=enable_ai)
            print("DEBUG: Analysis result type:", type(result))
            print("DEBUG: Analysis result:", result)

            # Save the analysis result for the logged-in user.
            if isinstance(result, dict):
                connection = get_db_connection()

                try:
                    connection.execute(
                        """
                        INSERT INTO analysis_history (
                            user_id,
                            submitted_code,
                            analysis_result,
                            health_score,
                            bugs_found
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            session["user_id"],
                            code,
                            json.dumps(result, default=str),
                            result.get("summary", {}).get("health_score"),
                            result.get("summary", {}).get("total_issues", 0),
                        ),
                    )

                    connection.commit()

                finally:
                    connection.close()

    ollama_info = {
        "model": get_ollama_model(),
        "url": get_ollama_url(),
    }

    return render_template(
        "index.html",
        result=result,
        code=code,
        ollama_info=ollama_info,
        enable_ai=enable_ai,
    )


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Asynchronous JSON API endpoint for fast deterministic analysis.
    Returns syntax, AST, static rules, sandboxed runtime, and health score in < 100ms.
    Payload: { "code": str, "enable_ai": bool (default: false) }
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            code = request.form.get("code", "")
            enable_ai = request.form.get("enable_ai", "false").lower() in ("true", "1", "on", "yes")
        else:
            code = data.get("code", "")
            enable_ai = bool(data.get("enable_ai", False))

        if not code or not code.strip():
            return jsonify({
                "success": False,
                "error": "No Python code was provided for analysis.",
            }), 400

        result = analyze_code(code, enable_ai=enable_ai)

        # Save the analysis result for the logged-in user.
        if "user_id" in session and isinstance(result, dict):
            connection = get_db_connection()

            try:
                summary = result.get("summary", {})

                connection.execute(
                    """
                    INSERT INTO analysis_history (
                        user_id,
                        submitted_code,
                        analysis_result,
                        health_score,
                        bugs_found
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        session["user_id"],
                        code,
                        json.dumps(result, default=str),
                        summary.get("health_score"),
                        summary.get("total_issues", 0),
                    ),
                )

                connection.commit()

            finally:
                connection.close()

        return jsonify({
            "success": True,
            "result": result,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": f"Analysis encountered an unexpected internal error: {exc}",
        }), 500


@app.route("/api/analyze-ai", methods=["POST"])
def api_analyze_ai():
    """
    Dedicated asynchronous AI generation endpoint.
    Called separately after deterministic results are displayed, so the user never waits.
    Payload: { "code": str, "detected_issues": list/dict }
    """
    try:
        data = request.get_json(silent=True) or {}
        code = data.get("code", "")
        detected_issues = data.get("detected_issues", {})

        if not code or not code.strip():
            return jsonify({
                "success": False,
                "error": "No Python code was provided for AI analysis.",
            }), 400

        ai_result = analyze_with_ai(code, detected_issues)
        return jsonify({
            "success": ai_result.get("success", False),
            "ai_analysis": ai_result,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": f"AI analysis failed with internal error: {exc}",
        }), 500


@app.route("/api/status", methods=["GET"])
def api_status():
    """
    Diagnostic status endpoint reporting server connection and model availability.
    Distinguishes server connectivity from model installation.
    """
    url = get_ollama_url()
    model = get_ollama_model()
    ollama_online = False
    models_available = []
    target_installed = False

    try:
        # Check base URL
        base_url = url.split("/api/")[0]
        tags_req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(tags_req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ollama_online = True
            models_available = [m.get("name", "") for m in data.get("models", [])]
            target_installed = any(model in m for m in models_available)
    except Exception:
        ollama_online = False

    if not ollama_online:
        generation_status = "offline"
    elif not target_installed:
        generation_status = "model_not_found"
    else:
        generation_status = "ready"

    return jsonify({
        "status": "healthy",
        "app": "BugLens",
        "version": "2.0.0",
        "ollama": {
            "online": ollama_online,
            "server": "connected" if ollama_online else "disconnected",
            "endpoint": url,
            "target_model": model,
            "target_model_installed": target_installed,
            "generation_status": generation_status,
            "available_models": models_available,
        },
    })


@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Endpoint not found."}), 404
    return render_template("home.html"), 404


@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Internal server error occurred."}), 500
    return render_template("home.html"), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)