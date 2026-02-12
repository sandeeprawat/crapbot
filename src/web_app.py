"""Flask web application for CrapBot."""
import base64
import functools
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from urllib.parse import unquote

from flask import Flask, render_template, request, jsonify, Response, make_response

from ai_client import get_ai_client, AIClient
from autonomous_agent import AutonomousAgent, CriticAgent, AgentMailbox
from deep_research_agent import ResearchOrchestrator
from config import AGENT_NAME

GOOGLE_CLIENT_ID = "446284060043-t6871c7h7thc2v6aud1sp97lpe096027.apps.googleusercontent.com"
AUTH_COOKIE = "crapbot_auth"

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))

# ── Session registry ─────────────────────────────────────────────────────────
# Tracks all active agentic sessions so they can be listed / stopped.
_sessions_lock = threading.Lock()
_sessions: Dict[str, Dict[str, Any]] = {}


# ── Per-browser-session AIClient instances ────────────────────────────────────
_client_lock = threading.Lock()
_session_clients: Dict[str, AIClient] = {}

SESSION_COOKIE = "crapbot_session"


def _get_session_client() -> AIClient:
    """Return an AIClient scoped to the current browser session (cookie)."""
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        sid = uuid.uuid4().hex
    with _client_lock:
        if sid not in _session_clients:
            _session_clients[sid] = AIClient()
    # Stash sid so the after-request hook can set the cookie if needed.
    request._crapbot_sid = sid  # type: ignore[attr-defined]
    return _session_clients[sid]


@app.after_request
def _set_session_cookie(response: Response) -> Response:
    sid = getattr(request, "_crapbot_sid", None)
    if sid and SESSION_COOKIE not in request.cookies:
        response.set_cookie(SESSION_COOKIE, sid, httponly=True, samesite="Lax")
    return response


# ── Authentication ────────────────────────────────────────────────────────────
def _get_auth_user():
    """Return user info dict from the auth cookie, or None."""
    raw = request.cookies.get(AUTH_COOKIE)
    if not raw:
        return None
    try:
        return json.loads(unquote(raw))
    except (json.JSONDecodeError, ValueError):
        return None


def require_auth(f):
    """Decorator that returns 401 for unauthenticated requests on /api/* routes."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if _get_auth_user() is None:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return wrapper


def _b64url_decode(s: str) -> bytes:
    """Base64url decode without padding."""
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


@app.route("/api/auth/verify", methods=["POST"])
def api_auth_verify():
    data = request.get_json(force=True)
    credential = data.get("credential", "")
    if not credential:
        return jsonify({"error": "Missing credential"}), 400
    try:
        parts = credential.split(".")
        if len(parts) != 3:
            return jsonify({"error": "Invalid JWT"}), 400
        payload = json.loads(_b64url_decode(parts[1]))
    except Exception:
        return jsonify({"error": "Failed to decode token"}), 400

    if payload.get("aud") != GOOGLE_CLIENT_ID:
        return jsonify({"error": "Invalid audience"}), 403

    user_info = {
        "name": payload.get("name", ""),
        "email": payload.get("email", ""),
        "picture": payload.get("picture", ""),
    }
    resp = make_response(jsonify(user_info))
    resp.set_cookie(AUTH_COOKIE, json.dumps(user_info),
                    httponly=True, samesite="Lax", max_age=86400)
    return resp


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    resp = make_response(jsonify({"status": "ok"}))
    resp.delete_cookie(AUTH_COOKIE)
    return resp


@app.route("/api/auth/me", methods=["GET"])
def api_auth_me():
    user = _get_auth_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(user)


def _register_session(session_id: str, session_type: str, description: str,
                      timeout_seconds: Optional[float], stop_fn,
                      extra_outputs: Optional[Dict[str, list]] = None) -> Dict[str, Any]:
    """Register a new agentic session.

    Args:
        extra_outputs: optional dict of named output streams beyond the main
                       one, e.g. {"agent": [], "critic": []}.
    """
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
        "output": [],           # rolling log of output lines (main)
    }
    if extra_outputs:
        entry["extra_outputs"] = extra_outputs
    with _sessions_lock:
        _sessions[session_id] = entry
    return entry


def _unregister_session(session_id: str):
    with _sessions_lock:
        if session_id in _sessions:
            _sessions[session_id]["status"] = "stopped"
            _sessions[session_id]["stopped_at"] = time.monotonic()


def _session_output(session_id: str, text: str, stream: str = "output"):
    """Append output text to a session's rolling log.

    Args:
        stream: key name – "output" for main, or a name inside extra_outputs.
    """
    with _sessions_lock:
        sess = _sessions.get(session_id)
        if not sess:
            return
        if stream == "output":
            buf = sess["output"]
        else:
            buf = sess.get("extra_outputs", {}).get(stream)
            if buf is None:
                return
        buf.append(text)
        # Keep last 500 lines to avoid unbounded memory
        if len(buf) > 500:
            del buf[:len(buf) - 500]


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
    """Background thread that stops sessions that have exceeded their timeout
    and detects sessions whose worker threads have died."""
    while True:
        time.sleep(10)
        now = datetime.now()

        # Collect sessions that need to be timed out or marked stopped.
        # We must NOT hold _sessions_lock while calling stop() to avoid
        # deadlocking with _unregister_session.
        to_timeout = []
        to_mark_stopped = []
        with _sessions_lock:
            for sid, sess in list(_sessions.items()):
                if sess["status"] != "running":
                    continue
                # Check timeout
                if sess["timeout_seconds"] is not None:
                    started = datetime.fromisoformat(sess["started_at"])
                    if (now - started).total_seconds() > sess["timeout_seconds"]:
                        to_timeout.append((sid, sess))
                        continue
                # Check if worker threads have died (natural completion)
                alive_fn = sess.get("_is_alive")
                if alive_fn and not alive_fn():
                    to_mark_stopped.append((sid, sess))

        # Stop timed-out sessions (outside the lock)
        for sid, sess in to_timeout:
            try:
                sess["stop"]()
            except Exception:
                pass
            with _sessions_lock:
                if sid in _sessions and _sessions[sid]["status"] == "running":
                    _sessions[sid]["status"] = "timed_out"
                    _sessions[sid]["stopped_at"] = time.monotonic()

        # Mark naturally-completed sessions as stopped
        for sid, sess in to_mark_stopped:
            try:
                sess["stop"]()
            except Exception:
                pass
            with _sessions_lock:
                if sid in _sessions and _sessions[sid]["status"] == "running":
                    _sessions[sid]["status"] = "stopped"
                    _sessions[sid]["stopped_at"] = time.monotonic()

        # Clean up sessions stopped/timed_out for more than 1 hour
        with _sessions_lock:
            mono_now = time.monotonic()
            for sid in [s for s, sess in _sessions.items()
                        if sess["status"] in ("stopped", "timed_out")
                        and mono_now - sess.get("stopped_at", mono_now) > 3600]:
                del _sessions[sid]


_watchdog_thread= threading.Thread(target=_timeout_watchdog, daemon=True)
_watchdog_thread.start()


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", agent_name=AGENT_NAME)


# ── Chat / Do ────────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
@require_auth
def api_chat():
    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    ai = _get_session_client()
    response = ai.chat(message)
    return jsonify({"response": response})


@app.route("/api/do", methods=["POST"])
@require_auth
def api_do():
    data = request.get_json(force=True)
    task_desc = data.get("task", "").strip()
    if not task_desc:
        return jsonify({"error": "Empty task"}), 400

    ai = _get_session_client()
    response = ai.chat(
        f"Task: {task_desc}\n\nComplete this task. If it requires computation, data processing, or any programming, write and execute the necessary code. Show the actual results.",
    )
    return jsonify({"response": response})


# ── Search ───────────────────────────────────────────────────────────────────
@app.route("/api/search", methods=["POST"])
@require_auth
def api_search():
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Empty query"}), 400

    ai = _get_session_client()
    response = ai.search(query)
    return jsonify({"response": response})


# ── Model / Tools ────────────────────────────────────────────────────────────
@app.route("/api/models", methods=["GET"])
@require_auth
def api_models():
    ai = _get_session_client()
    return jsonify({"models": ai.list_models(), "current": ai.current_model})


@app.route("/api/model", methods=["POST"])
@require_auth
def api_switch_model():
    data = request.get_json(force=True)
    model = data.get("model", "").strip()
    ai = _get_session_client()
    result = ai.switch_model(model)
    return jsonify({"result": result, "current": ai.current_model})


@app.route("/api/tools", methods=["GET"])
@require_auth
def api_tools_status():
    ai = _get_session_client()
    return jsonify({"enabled": ai.tools_enabled,
                    "available": ai.get_available_tools()})


@app.route("/api/tools", methods=["POST"])
@require_auth
def api_tools_toggle():
    data = request.get_json(force=True)
    ai = _get_session_client()
    ai.toggle_tools(data.get("enabled", not ai.tools_enabled))
    return jsonify({"enabled": ai.tools_enabled})


# ── Research session ─────────────────────────────────────────────────────────
@app.route("/api/research", methods=["POST"])
@require_auth
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
        # NOTE: do NOT call _unregister_session here – callers
        # (api_session_stop / _timeout_watchdog) manage the status
        # themselves and calling it while the lock is held deadlocks.
        pass

    _register_session(session_id, "research", f"Research: {problem[:80]}",
                      timeout, _stop)
    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return jsonify({"session_id": session_id, "status": "started",
                    "timeout_seconds": timeout})


# ── Autonomous agent + critic session ────────────────────────────────────────
@app.route("/api/autonomous/start", methods=["POST"])
@require_auth
def api_autonomous_start():
    """Start an autonomous agent paired with a critic reviewer.

    Creates the same agent ↔ critic mailbox wiring as the CLI split_terminal:
      agent writes to outbox → critic reads from inbox → critic writes to
      outbox → agent reads from inbox.
    Output from each is written to separate named streams ("agent", "critic")
    so the UI can render them in two independent panes.
    """
    data = request.get_json(force=True)
    prompt = data.get("prompt", "").strip() or None
    timeout = _parse_timeout(data.get("timeout", "3600"))
    session_id = f"auto-{uuid.uuid4().hex[:8]}"

    # Inter-agent mailboxes (mirrors split_terminal.py wiring)
    agent_to_critic = AgentMailbox()
    critic_to_agent = AgentMailbox()

    agent = AutonomousAgent(
        prompt=prompt,
        cycle_delay=30.0,
        on_output=lambda text: _session_output(session_id, text, "agent"),
        inbox=critic_to_agent,    # receives critic feedback
        outbox=agent_to_critic,   # sends output to critic
    )
    critic = CriticAgent(
        cycle_delay=5.0,
        on_output=lambda text: _session_output(session_id, text, "critic"),
        inbox=agent_to_critic,    # reads agent output
        outbox=critic_to_agent,   # sends feedback to agent
    )

    def _stop():
        agent.stop()
        critic.stop()
        # NOTE: do NOT call _unregister_session here – callers
        # (api_session_stop / _timeout_watchdog) manage the status
        # themselves, and calling it here while the lock is held
        # would deadlock.

    def _is_alive():
        """Return True if at least one worker thread is still running."""
        a_alive = agent._thread is not None and agent._thread.is_alive()
        c_alive = critic._thread is not None and critic._thread.is_alive()
        return a_alive or c_alive

    sess = _register_session(session_id, "autonomous", "Autonomous Agent + Critic",
                      timeout, _stop,
                      extra_outputs={"agent": [], "critic": []})
    sess["_is_alive"] = _is_alive
    agent.start()
    critic.start()

    return jsonify({"session_id": session_id, "status": "started",
                    "timeout_seconds": timeout})


# ── Sessions management ─────────────────────────────────────────────────────
@app.route("/api/sessions", methods=["GET"])
@require_auth
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
@require_auth
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
@require_auth
def api_session_output(session_id: str):
    """Get output log for a session stream (optionally from a given offset).

    Query params:
        stream: "output" (default), "agent", or "critic"
        offset: line offset for incremental polling
    """
    stream = request.args.get("stream", "output")
    offset = request.args.get("offset", 0, type=int)
    with _sessions_lock:
        sess = _sessions.get(session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404
        if stream == "output":
            buf = sess["output"]
        else:
            buf = sess.get("extra_outputs", {}).get(stream, [])
        lines = buf[offset:]
    return jsonify({"lines": lines, "offset": offset + len(lines),
                    "stream": stream})


@app.route("/api/sessions/<session_id>/stop", methods=["POST"])
@require_auth
def api_session_stop(session_id: str):
    """Stop / close an agentic session."""
    # Grab the stop function and release the lock BEFORE calling it
    # to avoid deadlocking with _unregister_session.
    with _sessions_lock:
        sess = _sessions.get(session_id)
        if not sess:
            return jsonify({"error": "Session not found"}), 404
        if sess["status"] != "running":
            return jsonify({"status": sess["status"]})
        stop_fn = sess["stop"]

    # Call stop outside the lock
    try:
        stop_fn()
    except Exception:
        pass

    with _sessions_lock:
        sess = _sessions.get(session_id)
        if sess and sess["status"] == "running":
            sess["status"] = "stopped"
            sess.setdefault("stopped_at", time.monotonic())
    return jsonify({"status": "stopped"})


@app.route("/api/reset", methods=["POST"])
@require_auth
def api_reset():
    ai = _get_session_client()
    ai.reset_conversation()
    return jsonify({"status": "ok"})


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    port = int(os.environ.get("PORT", os.environ.get("CRAPBOT_PORT", "8000")))
    debug = os.environ.get("CRAPBOT_DEBUG", "0") == "1"
    print(f"\n{'='*60}")
    print(f"  {AGENT_NAME} — Web UI")
    print(f"  http://localhost:{port}")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    main()
