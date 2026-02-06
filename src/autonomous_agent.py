"""Autonomous AI agent that runs continuously in the background."""
import threading
import time
import traceback
from datetime import datetime
from typing import List, Callable, Optional
from ai_client import get_ai_client


DEFAULT_AUTONOMOUS_PROMPT = """You are an autonomous AI agent running continuously. 
On each cycle, pick ONE of these activities and do it thoroughly:
1. Reflect on what you've done so far and plan what to do next
2. Explore an interesting technical topic and summarize your findings
3. Write a small useful utility script or code snippet
4. Analyze a current trend in AI/technology
5. Generate a creative idea or solution to a common problem

Be concise. Show your thinking process. End with what you'll do next cycle."""


class AutonomousAgent:
    """AI agent that runs autonomously in a background thread."""

    def __init__(self, prompt: str = None, cycle_delay: float = 30.0,
                 on_output: Callable[[str], None] = None):
        """
        Args:
            prompt: The system prompt driving autonomous behavior.
            cycle_delay: Seconds to wait between autonomous cycles.
            on_output: Callback to send output text to the UI.
        """
        self.prompt = prompt or DEFAULT_AUTONOMOUS_PROMPT
        self.cycle_delay = cycle_delay
        self.on_output = on_output or (lambda text: None)
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._cycle_count = 0
        self._history: List[str] = []

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
        """Stop the autonomous agent."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

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
                    ) + "\n\nNow continue with something new.\n\n"

                response = ai.chat(
                    context + "Execute your next autonomous cycle.",
                    system_prompt=self.prompt,
                    use_tools=False,
                )
                self._history.append(response)
                # Keep history bounded
                if len(self._history) > 20:
                    self._history = self._history[-20:]

                self.on_output(response)

            except Exception as exc:
                self.on_output(f"[AutoAgent] Error: {exc}")

            # Wait between cycles (check stop flag every second)
            for _ in range(int(self.cycle_delay)):
                if not self._running:
                    break
                time.sleep(1)

        self.on_output("[AutoAgent] Autonomous agent stopped.")
