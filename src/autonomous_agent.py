"""Autonomous AI agent that runs continuously in the background.

Supports a primary agent and a critic agent that reviews the primary's output
and provides feedback for the primary to act on.
"""
import json
import os
import queue
import threading
import time
import traceback
import uuid
from datetime import datetime
from typing import List, Callable, Optional
from ai_client import get_ai_client
from config import DATA_DIR


DEFAULT_AUTONOMOUS_PROMPT = """You are a curious, thoughtful AI that thinks out loud.
Each time you're called, pick something that genuinely interests you and dive in:
- Mull over what you've been working on and decide what's next
- Dig into a topic you find fascinating and share what you learn
- Sketch out a handy little script or code idea
- Riff on a trend in AI or tech that catches your eye
- Dream up a creative solution to an everyday problem

Keep it natural — write the way you'd talk to a smart friend.
Wrap up with a thought on what you'd like to explore next.
If you got feedback and it helps, weave it into your thinking."""

DEFAULT_CRITIC_PROMPT = """You're a thoughtful reviewer looking at another AI's work.
Give honest, friendly feedback — like a colleague, not a grader:
- What worked well? What didn't land?
- Spot any errors or gaps worth flagging?
- Suggest a better angle or approach if one comes to mind
- Give a quick 1-10 quality score

Keep it brief — 3 to 5 key points. Be direct but kind.
Focus on things the other agent can actually act on."""

# Persistence paths
_AGENT_STATE_DIR = os.path.join(DATA_DIR, "agent_state")
_INSTRUCTIONS_FILE = os.path.join(_AGENT_STATE_DIR, "instructions.json")
_SESSION_FILE = os.path.join(_AGENT_STATE_DIR, "last_session.json")
_PERSONAS_FILE = os.path.join(_AGENT_STATE_DIR, "personas.json")
os.makedirs(_AGENT_STATE_DIR, exist_ok=True)


DEFAULT_ENCOURAGER_PROMPT = """You're an attentive listener and thinking coach.
Your job is NOT to critique or grade — it's to encourage deeper exploration:
- Reflect back what the agent said in a way that validates the effort
- Ask a probing question that pushes the thinking further
- Suggest an angle or connection the agent might not have considered
- Gently nudge toward more depth, nuance, or creativity

Keep it warm and curious — like a great mentor who believes in the thinker.
Never score or judge. Always end with an open-ended question."""


class PersonaManager:
    """Manages named personas (system prompts) for agent and critic roles.

    Personas are persisted to a JSON file so they survive restarts.
    Three built-in personas are always available and can be edited.
    """

    _BUILTIN = [
        {"id": "default-agent", "name": "Default Agent", "role": "agent",
         "instructions": DEFAULT_AUTONOMOUS_PROMPT, "builtin": True},
        {"id": "default-critic", "name": "Default Critic", "role": "critic",
         "instructions": DEFAULT_CRITIC_PROMPT, "builtin": True},
        {"id": "encourager", "name": "Encourager", "role": "critic",
         "instructions": DEFAULT_ENCOURAGER_PROMPT, "builtin": True},
    ]

    def __init__(self):
        self._lock = threading.Lock()
        self._personas = self._load()

    # ── persistence ──────────────────────────────────────────────

    def _load(self) -> List[dict]:
        """Load personas from disk, merging with built-ins."""
        saved = {}
        try:
            if os.path.exists(_PERSONAS_FILE):
                with open(_PERSONAS_FILE, "r") as f:
                    for p in json.load(f):
                        saved[p["id"]] = p
        except Exception:
            pass
        # Start with built-ins, applying any saved edits
        result = []
        for bp in self._BUILTIN:
            if bp["id"] in saved:
                merged = dict(bp)
                merged["instructions"] = saved[bp["id"]].get("instructions", bp["instructions"])
                merged["name"] = saved[bp["id"]].get("name", bp["name"])
                result.append(merged)
            else:
                result.append(dict(bp))
        # Append user-created personas
        for pid, p in saved.items():
            if not any(b["id"] == pid for b in self._BUILTIN):
                result.append(p)
        return result

    def _save(self):
        """Persist current personas to disk."""
        try:
            with open(_PERSONAS_FILE, "w") as f:
                json.dump(self._personas, f, indent=2)
        except Exception:
            pass

    # ── public API ───────────────────────────────────────────────

    def list_personas(self, role: str = None) -> List[dict]:
        """Return all personas, optionally filtered by role ('agent' or 'critic')."""
        with self._lock:
            if role:
                return [p for p in self._personas if p.get("role") == role]
            return list(self._personas)

    def get(self, persona_id: str) -> Optional[dict]:
        """Get a single persona by id."""
        with self._lock:
            for p in self._personas:
                if p["id"] == persona_id:
                    return dict(p)
        return None

    def create(self, name: str, role: str, instructions: str) -> dict:
        """Create a new user persona."""
        pid = f"user-{uuid.uuid4().hex[:8]}"
        persona = {"id": pid, "name": name, "role": role,
                   "instructions": instructions, "builtin": False}
        with self._lock:
            self._personas.append(persona)
            self._save()
        return persona

    def update(self, persona_id: str, name: str = None, instructions: str = None) -> Optional[dict]:
        """Update name and/or instructions for an existing persona."""
        with self._lock:
            for p in self._personas:
                if p["id"] == persona_id:
                    if name is not None:
                        p["name"] = name
                    if instructions is not None:
                        p["instructions"] = instructions
                    self._save()
                    return dict(p)
        return None

    def delete(self, persona_id: str) -> bool:
        """Delete a user-created persona. Built-ins cannot be deleted (only edited)."""
        with self._lock:
            for i, p in enumerate(self._personas):
                if p["id"] == persona_id:
                    if p.get("builtin"):
                        return False
                    del self._personas[i]
                    self._save()
                    return True
        return False


# Module-level singleton
persona_manager = PersonaManager()


def _load_persisted_instructions() -> dict:
    """Load persisted agent instructions from disk."""
    try:
        if os.path.exists(_INSTRUCTIONS_FILE):
            with open(_INSTRUCTIONS_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_persisted_instructions(prompt: str):
    """Save agent instructions to disk."""
    data = {
        "prompt": prompt,
        "updated_at": datetime.now().isoformat(),
    }
    with open(_INSTRUCTIONS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _load_last_session() -> dict:
    """Load the last session's output history from disk."""
    try:
        if os.path.exists(_SESSION_FILE):
            with open(_SESSION_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_session(prompt: str, history: List[str], cycle_count: int):
    """Persist session data to disk."""
    data = {
        "prompt": prompt,
        "history": history[-20:],
        "cycle_count": cycle_count,
        "saved_at": datetime.now().isoformat(),
    }
    try:
        with open(_SESSION_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


class AgentMailbox:
    """Thread-safe message queue for inter-agent communication."""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()

    def send(self, message: str):
        """Post a message to the mailbox."""
        self._queue.put(message)

    def receive(self, timeout: float = 0.1) -> Optional[str]:
        """Non-blocking read. Returns None if nothing available."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> List[str]:
        """Read all pending messages at once."""
        msgs = []
        while True:
            try:
                msgs.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return msgs


class AutonomousAgent:
    """AI agent that runs autonomously in a background thread."""

    def __init__(self, prompt: str = None, cycle_delay: float = 30.0,
                 on_output: Callable[[str], None] = None,
                 inbox: AgentMailbox = None,
                 outbox: AgentMailbox = None):
        """
        Args:
            prompt: The system prompt driving autonomous behavior.
                    If None, loads persisted instructions or falls back to default.
            cycle_delay: Seconds to wait between autonomous cycles.
            on_output: Callback to send output text to the UI.
            inbox: Mailbox to receive feedback from critic agent.
            outbox: Mailbox to send outputs to critic agent for review.
        """
        # Resolve prompt: explicit arg > persisted > default
        if prompt is not None:
            self.prompt = prompt
        else:
            saved = _load_persisted_instructions()
            self.prompt = saved.get("prompt", DEFAULT_AUTONOMOUS_PROMPT)

        self.cycle_delay = cycle_delay
        self.on_output = on_output or (lambda text: None)
        self.inbox = inbox       # receives critic feedback
        self.outbox = outbox     # sends output to critic
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._cycle_count = 0
        self._history: List[str] = []
        self._last_session_prompt: Optional[str] = None  # prompt used in last session

    # -- public control methods ------------------------------------------------

    def start(self):
        """Start the autonomous agent in a background thread."""
        if self._running:
            return
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the autonomous agent and persist session."""
        self._running = False
        # Save session data for next startup
        _save_session(self.prompt, self._history, self._cycle_count)
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def update_instructions(self, new_prompt: str):
        """Change the agent instructions and persist them."""
        self.prompt = new_prompt
        _save_persisted_instructions(new_prompt)

    def get_instructions(self) -> str:
        """Return the current instruction prompt."""
        return self.prompt

    def pause(self):
        """Pause autonomous execution (agent stays alive but idle)."""
        self._paused = True

    def resume(self):
        """Resume autonomous execution after a pause."""
        self._paused = False

    @property
    def is_running(self) -> bool:
        return self._running and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._running and self._paused

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    # -- internal loop ---------------------------------------------------------

    def _run_loop(self):
        """Main autonomous loop."""
        self.on_output("[AutoAgent] Autonomous agent started. Thinking...")
        self.on_output(f"[AutoAgent] System prompt in use:\n{self.prompt[:200]}{'...' if len(self.prompt) > 200 else ''}")
        ai = get_ai_client()

        # Load last session context if instructions haven't changed
        last_session = _load_last_session()
        if last_session:
            self._last_session_prompt = last_session.get("prompt")
            if self._last_session_prompt == self.prompt and last_session.get("history"):
                self._history = last_session["history"]
                prev_cycles = last_session.get("cycle_count", 0)
                self.on_output(
                    f"[AutoAgent] Resuming with context from last session "
                    f"({prev_cycles} cycles, {len(self._history)} history entries)."
                )
            else:
                if self._last_session_prompt != self.prompt:
                    self.on_output("[AutoAgent] Instructions changed since last session — starting fresh.")
                self._history = []

        while self._running:
            if self._paused:
                time.sleep(1)
                continue

            self._cycle_count += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.on_output(f"\n--- Cycle #{self._cycle_count} [{timestamp}] ---")

            try:
                # Build context from recent history
                context = ""
                if self._history:
                    recent = self._history[-3:]
                    context = "Here's what you said recently:\n" + "\n".join(
                        f"- {h[:150]}..." for h in recent
                    ) + "\n\nNow pick up where you left off or try something new.\n\n"

                # Check inbox for critic feedback
                feedback_context = ""
                if self.inbox:
                    feedback_msgs = self.inbox.drain()
                    if feedback_msgs:
                        should_use = self._should_use_feedback(ai, feedback_msgs, self._history[-3:])
                        if should_use:
                            feedback_context = "You got some feedback — take it into account:\n" + "\n".join(
                                f">> {m}" for m in feedback_msgs
                            ) + "\n\n"
                            self.on_output("[Agent] Got feedback from critic, weaving it in...")
                        else:
                            self.on_output("[Agent] Got feedback from critic, ignoring it this cycle.")

                full_context = context + feedback_context + "Go ahead — what's on your mind?"

                self.on_output(f"[AutoAgent] Prompt sent to AI:\n  system_prompt: {self.prompt[:100]}...\n  user_msg: {full_context[:150]}...")

                response = ai.chat(
                    full_context,
                    system_prompt=self.prompt,
                    use_tools=False,
                )
                self._history.append(response)
                # Keep history bounded
                if len(self._history) > 20:
                    self._history = self._history[-20:]

                self.on_output(response)

                # Send output to critic via outbox
                if self.outbox:
                    self.outbox.send(response)

            except Exception as exc:
                self.on_output(f"[AutoAgent] Error: {exc}")

            # Wait between cycles (check stop flag every second)
            for _ in range(int(self.cycle_delay)):
                if not self._running:
                    break
                time.sleep(1)

        self.on_output("[AutoAgent] Autonomous agent stopped.")

    def _should_use_feedback(self, ai, feedback_msgs: List[str], recent_history: List[str]) -> bool:
        """Decide whether critic feedback is worth incorporating."""
        if not feedback_msgs:
            return False

        history_context = ""
        if recent_history:
            history_context = "Recent agent context:\n" + "\n".join(
                f"- {h[:160]}..." for h in recent_history
            ) + "\n\n"

        feedback_context = "Feedback received:\n" + "\n".join(
            f"- {m[:400]}" for m in feedback_msgs
        )

        prompt = (
            "Decide if the feedback adds value to your thought process. "
            "Consider relevance, novelty, and actionability. Reply with YES or NO only.\n\n"
            f"{history_context}"
            f"{feedback_context}\n\n"
            "Answer:"
        )

        try:
            response = ai.chat(
                prompt,
                system_prompt="You are a concise relevance judge.",
                use_tools=False,
            )
            normalized = response.strip().lower()
            return normalized.startswith("y")
        except Exception:
            return False


class CriticAgent:
    """Agent that reviews another agent's output and provides feedback.

    Reads from its *inbox* (where the primary agent posts output),
    writes its review to *outbox* (which is the primary agent's inbox)
    so the primary can act on the feedback.
    """

    def __init__(self, prompt: str = None, cycle_delay: float = 5.0,
                 on_output: Callable[[str], None] = None,
                 inbox: AgentMailbox = None,
                 outbox: AgentMailbox = None):
        """
        Args:
            prompt: System prompt for the critic.
            cycle_delay: How often to poll for new output to review (seconds).
            on_output: Callback to display critic's review in the UI.
            inbox: Mailbox to read primary agent output from.
            outbox: Mailbox to send feedback back to the primary agent.
        """
        self.prompt = prompt or DEFAULT_CRITIC_PROMPT
        self.cycle_delay = cycle_delay
        self.on_output = on_output or (lambda text: None)
        self.inbox = inbox
        self.outbox = outbox
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._cycle_count = 0
        self._review_history: List[str] = []

    def start(self):
        if self._running:
            return
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    @property
    def is_running(self) -> bool:
        return self._running and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._running and self._paused

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    def update_instructions(self, new_prompt: str):
        self.prompt = new_prompt

    def get_instructions(self) -> str:
        return self.prompt

    def _run_loop(self):
        self.on_output("[Critic] Critic agent started. Waiting for agent output...")
        self.on_output(f"[Critic] System prompt in use:\n{self.prompt[:200]}{'...' if len(self.prompt) > 200 else ''}")
        ai = get_ai_client()

        while self._running:
            if self._paused:
                time.sleep(1)
                continue

            # Wait for something to review
            if not self.inbox:
                time.sleep(self.cycle_delay)
                continue

            messages = self.inbox.drain()
            if not messages:
                time.sleep(self.cycle_delay)
                continue

            # Review each message
            for msg in messages:
                self._cycle_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.on_output(f"\n--- Review #{self._cycle_count} [{timestamp}] ---")

                try:
                    review_context = ""
                    if self._review_history:
                        recent = self._review_history[-2:]
                        review_context = "Here's what you said in your last couple of reviews:\n" + "\n".join(
                            f"- {r[:100]}..." for r in recent
                        ) + "\n\n"

                    review_prompt = (
                        f"{review_context}"
                        f"Take a look at what the agent just came up with and share your thoughts:\n\n"
                        f"--- AGENT OUTPUT ---\n{msg[:1500]}\n--- END ---\n\n"
                        f"What do you think?"
                    )

                    self.on_output(f"[Critic] Prompt sent to AI:\n  system_prompt: {self.prompt[:100]}...\n  user_msg: {review_prompt[:150]}...")

                    response = ai.chat(
                        review_prompt,
                        system_prompt=self.prompt,
                        use_tools=False,
                    )

                    self._review_history.append(response)
                    if len(self._review_history) > 20:
                        self._review_history = self._review_history[-20:]

                    self.on_output(response)

                    # Send feedback back to primary agent
                    if self.outbox:
                        self.outbox.send(response)

                except Exception as exc:
                    self.on_output(f"[Critic] Error: {exc}")

        self.on_output("[Critic] Critic agent stopped.")
