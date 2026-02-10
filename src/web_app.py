"""Flask web application for CrapBot."""
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from flask import Flask, render_template, request, jsonify, Response

from ai_client import get_ai_client
from autonomous_agent import AutonomousAgent, CriticAgent, AgentMailbox
from deep_research_agent import ResearchOrchestrator
from config import AGENT_NAME

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))

# ── Session registry ─────────────────────────────────────────────────────────
# Tracks all active agentic sessions so they can be listed / stopped.
_sessions_lock = threading.Lock()
_sessions: Dict[str, Dict[str, Any]] = {}


def _register_session(session_id: str, session_type: str, description: str,
                      timeout_seconds: Optional[float], stop_fn) -> Dict[str, Any]:
    """Register a new agentic session."""
    entry = {
        "id": session_id,
        "type": session_type,
        "description": description,
        "started_at": datetime.now().isoformat(),
        "timeout_seconds": timeout_seconds,
        "expires_at": (datetime.now() + timedelta(seconds=timeout_seconds)).isoformat()
                      if timeout_seconds else None,
        "status": "running",
        "stop": stop_fn,        # callable – not serialised
        "output": [],           # rolling log of output lines
    }
    with _sessions_lock:
        _sessions[session_id] = entry
    return entry


def _unregister_session(session_id: str):
    with _sessions_lock:
        if session_id in _sessions:
            _sessions[session_id]["status"] = "stopped"


def _session_output(session_id: str, text: str):
    """Append output text to a session's rolling log."""
    with _sessions_lock:
        if session_id in _sessions:
            _sessions[session_id]["output"].append(text)
            # Keep last 200 lines to avoid unbounded memory
            if len(_sessions[session_id]["output"]) > 200:
                _sessions[session_id]["output"] = _sessions[session_id]["output"][-200:]


def _parse_timeout(value: str) -> Optional[float]:
    """Parse a timeout string into seconds. Returns None for unlimited."""
    if not value or value.lower() == "unlimited":
        return None
    try:
        num = float(value)
        return num if num > 0 else None
    except (ValueError, TypeError):
        return 3600.0  # default 1 hour


# ── Timeout watchdog ─────────────────────────────────────────────────────────
def _timeout_watchdog():
    """Background thread that stops sessions that have exceeded their timeout."""
    while True:
        time.sleep(10)
        now = datetime.now()
        with _sessions_lock:
            for sid, sess in list(_sessions.items()):
                if sess["status"] != "running":
                    continue
                if sess["timeout_seconds"] is None:
                    continue  # unlimited
                started = datetime.fromisoformat(sess["started_at"])
                if (now - started).total_seconds() > sess["timeout_seconds"]:
                    try:
                        sess["stop"]()
                    except Exception:
                        pass
                    sess["status"] = "timed_out"


_watchdog_thread = threading.Thread(target=_timeout_watchdog, daemon=True)
_watchdog_thread.start()


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", agent_name=AGENT_NAME)


# ── Chat / Do ────────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    ai = get_ai_client()
    response = ai.chat(message)
    return jsonify({"response": response})


@app.route("/api/do", methods=["POST"])
def api_do():
    data = request.get_json(force=True)
    task_desc = data.get("task", "").strip()
    if not task_desc:
        return jsonify({"error": "Empty task"}), 400

    ai = get_ai_client()
    response = ai.chat(
        f"Task: {task_desc}\n\nComplete this task. If it requires computation, data processing, or any programming, write and execute the necessary code. Show the actual results.",
    )
    return jsonify({"response": response})


# ── Search ───────────────────────────────────────────────────────────────────
@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Empty query"}), 400

    ai = get_ai_client()
    response = ai.search(query)
    return jsonify({"response": response})


# ── Model / Tools ────────────────────────────────────────────────────────────
@app.route("/api/models", methods=["GET"])
def api_models():
    ai = get_ai_client()
    return jsonify({"models": ai.list_models(), "current": ai.current_model})


@app.route("/api/model", methods=["POST"])
def api_switch_model():
    data = request.get_json(force=True)
    model = data.get("model", "").strip()
    ai = get_ai_client()
    result = ai.switch_model(model)
    return jsonify({"result": result, "current": ai.current_model})


@app.route("/api/tools", methods=["GET"])
def api_tools_status():
    ai = get_ai_client()
    return jsonify({"enabled": ai.tools_enabled,
                    "available": ai.get_available_tools()})


@app.route("/api/tools", methods=["POST"])
def api_tools_toggle():
    data = request.get_json(force=True)
    ai = get_ai_client()
    ai.toggle_tools(data.get("enabled", not ai.tools_enabled))
    return jsonify({"enabled": ai.tools_enabled})


# ── Research session ─────────────────────────────────────────────────────────
@app.route("/api/research", methods=["POST"])
def api_research():
    """Start a deep research session in the background."""
    data = request.get_json(force=True)
    problem = data.get("problem", "").strip()
    if not problem:
        return jsonify({"error": "Empty problem"}), 400

    timeout = _parse_timeout(data.get("timeout", "3600"))
    session_id = f"research-{uuid.uuid4().hex[:8]}"

    # Orchestrator will run in a background thread
    orchestrator = ResearchOrchestrator(
        on_output=lambda text: _session_output(session_id, text)
    )

    def _run():
        try:
            _session_output(session_id, f"[Research] Starting research: {problem}")
            result = orchestrator.conduct_research(problem)
            _session_output(session_id, "[Research] ✓ Research complete.")
            with _sessions_lock:
                if session_id in _sessions:
                    _sessions[session_id]["result"] = result
        except Exception as exc:
            _session_output(session_id, f"[Research] Error: {exc}")
        finally:
            _unregister_session(session_id)

    def _stop():
        _unregister_session(session_id)

    _register_session(session_id, "research", f"Research: {problem[:80]}",
                      timeout, _stop)
    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return jsonify({"session_id": session_id, "status": "started",
                    "timeout_seconds": timeout})


# ── Autonomous agent session ────────────────────────────────────────────────
@app.route("/api/autonomous/start", methods=["POST"])
def api_autonomous_start():
    """Start an autonomous agent session (does NOT auto-start)."""
    data = request.get_json(force=True)
    prompt = data.get("prompt", "").strip() or None
    timeout = _parse_timeout(data.get("timeout", "3600"))
    session_id = f"auto-{uuid.uuid4().hex[:8]}"

    agent = AutonomousAgent(
        prompt=prompt,
        cycle_delay=30.0,
        on_output=lambda text: _session_output(session_id, text),
    )

    def _stop():
        agent.stop()
        _unregister_session(session_id)

    _register_session(session_id, "autonomous", "Autonomous Agent",
                      timeout, _stop)
    agent.start()

    return jsonify({"session_id": session_id, "status": "started",
                    "timeout_seconds": timeout})


# ── Sessions management ─────────────────────────────────────────────────────
@app.route("/api/sessions", methods=["GET"])
def api_sessions():
    """List all agentic sessions."""
    with _sessions_lock:
        out = []
        for s in _sessions.values():
            out.append({
                "id": s["id"],
                "type": s["type"],
                "description": s["description"],
                "started_at": s["started_at"],
                "timeout_seconds": s["timeout_seconds"],
                "expires_at": s["expires_at"],
                "status": s["status"],
            })
    return jsonify({"sessions": out})


@app.route("/api/sessions/<session_id>", methods=["GET"])
def api_session_detail(session_id: str):
    """Get session detail including output log."""
    with _sessions_lock:
        sess = _sessions.get(session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404
        return jsonify({
            "id": sess["id"],
            "type": sess["type"],
            "description": sess["description"],
            "started_at": sess["started_at"],
            "timeout_seconds": sess["timeout_seconds"],
            "expires_at": sess["expires_at"],
            "status": sess["status"],
            "output": sess["output"],
        })


@app.route("/api/sessions/<session_id>/output", methods=["GET"])
def api_session_output(session_id: str):
    """Get only the output log (optionally from a given offset)."""
    offset = request.args.get("offset", 0, type=int)
    with _sessions_lock:
        sess = _sessions.get(session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404
        lines = sess["output"][offset:]
    return jsonify({"lines": lines, "offset": offset + len(lines)})


@app.route("/api/sessions/<session_id>/stop", methods=["POST"])
def api_session_stop(session_id: str):
    """Stop / close an agentic session."""
    with _sessions_lock:
        sess = _sessions.get(session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404
        if sess["status"] == "running":
            try:
                sess["stop"]()
            except Exception:
                pass
            sess["status"] = "stopped"
    return jsonify({"status": "stopped"})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    ai = get_ai_client()
    ai.reset_conversation()
    return jsonify({"status": "ok"})


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    port = int(os.environ.get("CRAPBOT_PORT", 5000))
    debug = os.environ.get("CRAPBOT_DEBUG", "0") == "1"
    print(f"\n{'='*60}")
    print(f"  {AGENT_NAME} — Web UI")
    print(f"  http://localhost:{port}")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    main()
