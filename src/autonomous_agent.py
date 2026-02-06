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
from datetime import datetime
from typing import List, Callable, Optional
from ai_client import get_ai_client
from config import DATA_DIR


DEFAULT_AUTONOMOUS_PROMPT = """You are an autonomous AI agent running continuously. 
On each cycle, pick ONE of these activities and do it thoroughly:
1. Reflect on what you've done so far and plan what to do next
2. Explore an interesting technical topic and summarize your findings
3. Write a small useful utility script or code snippet
4. Analyze a current trend in AI/technology
5. Generate a creative idea or solution to a common problem

Be concise. Show your thinking process. End with what you'll do next cycle.
If you receive critic feedback, address it in your next cycle."""

DEFAULT_CRITIC_PROMPT = """You are a critic agent that reviews the output of another AI agent.
Your job is to:
1. Evaluate the quality, accuracy, and usefulness of the agent's output
2. Point out any errors, logical flaws, or missed opportunities
3. Suggest specific improvements or alternative approaches
4. Rate the output on a scale of 1-10

Be constructive but honest. Be concise - keep feedback to 3-5 key points.
Focus on actionable feedback the agent can use to improve."""

# Persistence paths
_AGENT_STATE_DIR = os.path.join(DATA_DIR, "agent_state")
_INSTRUCTIONS_FILE = os.path.join(_AGENT_STATE_DIR, "instructions.json")
_SESSION_FILE = os.path.join(_AGENT_STATE_DIR, "last_session.json")
os.makedirs(_AGENT_STATE_DIR, exist_ok=True)


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
                    context = "Your recent outputs:\n" + "\n".join(
                        f"- {h[:150]}..." for h in recent
                    ) + "\n\n"

                # Check inbox for critic feedback
                feedback_context = ""
                if self.inbox:
                    feedback_msgs = self.inbox.drain()
                    if feedback_msgs:
                        feedback_context = "CRITIC FEEDBACK (address this):\n" + "\n".join(
                            f">> {m}" for m in feedback_msgs
                        ) + "\n\n"
                        self.on_output("[Agent] Received critic feedback, incorporating...")

                full_context = context + feedback_context + "Execute your next autonomous cycle."

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
                        review_context = "Your recent reviews:\n" + "\n".join(
                            f"- {r[:100]}..." for r in recent
                        ) + "\n\n"

                    review_prompt = (
                        f"{review_context}"
                        f"Review this agent output and provide constructive feedback:\n\n"
                        f"--- AGENT OUTPUT ---\n{msg[:1500]}\n--- END ---\n\n"
                        f"Provide your critique."
                    )

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
