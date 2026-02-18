"""Split-screen terminal UI using curses.

Two-column layout:
  Left pane:         interactive user input (commands / chat) — control panel
  Right-top pane:    autonomous AI agent output (runs continuously)
  Right-bottom pane: critic AI agent output (reviews primary agent, provides feedback)
"""
import curses
import os
import subprocess
import tempfile
import threading
import textwrap
import time
from collections import deque
from datetime import datetime
from ai_client import get_ai_client
from task_manager import get_task_manager, list_task_folders
from autonomous_tasks import add_scheduled_task, remove_scheduled_task, list_configured_tasks
from autonomous_agent import AutonomousAgent, CriticAgent, AgentMailbox, _SESSION_FILE
from deep_research_agent import run_deep_research
from config import AGENT_NAME


# Maximum lines kept in each pane's buffer
MAX_BUFFER_LINES = 500


class PaneBuffer:
    """Thread-safe scrollable text buffer for a pane."""

    def __init__(self, maxlines: int = MAX_BUFFER_LINES):
        self._lines: deque = deque(maxlen=maxlines)
        self._lock = threading.Lock()

    def add(self, text: str):
        with self._lock:
            for line in text.split("\n"):
                self._lines.append(line)

    def get_lines(self) -> list:
        with self._lock:
            return list(self._lines)

    def clear(self):
        with self._lock:
            self._lines.clear()


def get_multiline_input(initial_text: str = "") -> str:
    """Open a temporary file in the user's editor for multi-line text input.
    
    Args:
        initial_text: Optional initial text to populate the editor with.
        
    Returns:
        The text entered by the user, or empty string if cancelled.
    """
    editor = os.environ.get('EDITOR', os.environ.get('VISUAL', 'nano'))
    
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tf:
        temp_path = tf.name
        if initial_text:
            tf.write(initial_text)
            tf.write("\n\n# Enter your multi-line text above this line.\n")
            tf.write("# Lines starting with # will be ignored.\n")
        else:
            tf.write("# Enter your multi-line text below.\n")
            tf.write("# Lines starting with # will be ignored.\n")
            tf.write("# Save and close the editor when done.\n\n")
        tf.flush()
    
    try:
        # Open the editor
        subprocess.call([editor, temp_path])
        
        # Read the content back
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        # Filter out comment lines and strip trailing whitespace
        content_lines = [line.rstrip() for line in lines if not line.strip().startswith('#')]
        content = '\n'.join(content_lines).strip()
        
        return content
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except:
            pass


class SplitTerminal:
    """Curses-based split-screen terminal: left control + right stacked agent/critic."""

    def __init__(self):
        self.ai = get_ai_client()
        self.tasks = get_task_manager()
        self.left_buf = PaneBuffer()
        self.agent_buf = PaneBuffer()   # right-top: autonomous agent
        self.critic_buf = PaneBuffer()  # right-bottom: critic agent
        self.input_line = ""
        self.input_history: list = []
        self.input_hist_idx = -1
        self.running = False

        # Scroll state for right panes (0 = pinned to bottom / auto-scroll)
        self._agent_scroll = 0   # lines scrolled up from bottom
        self._critic_scroll = 0
        self._focused_pane = "agent"  # which right pane receives scroll keys

        # Inter-agent communication
        self.agent_to_critic = AgentMailbox()  # primary -> critic
        self.critic_to_agent = AgentMailbox()  # critic -> primary

        self.auto_agent: AutonomousAgent = None
        self.critic_agent: CriticAgent = None
        self._stdscr = None

        # Commands (same set as old Terminal, plus agent controls)
        self.commands = {
            "help": self.cmd_help,
            "chat": self.cmd_chat,
            "search": self.cmd_search,
            "model": self.cmd_model,
            "models": self.cmd_models,
            "tools": self.cmd_tools,
            "reset": self.cmd_reset,
            "task": self.cmd_task,
            "tasks": self.cmd_list_tasks,
            "schedule": self.cmd_schedule,
            "status": self.cmd_status,
            "history": self.cmd_history,
            "outputs": self.cmd_outputs,
            "cancel": self.cmd_cancel,
            "do": self.cmd_do,
            "research": self.cmd_research,
            "stop": self.cmd_stop_agent,
            "start": self.cmd_start_agent,
            "pause": self.cmd_pause_agent,
            "resume": self.cmd_resume_agent,
            "instruct": self.cmd_instruct_agent,
            "topic": self.cmd_topic,
            "fresh": self.cmd_fresh_restart,
            "clear": self.cmd_clear,
            "agents": self.cmd_agents_status,
            "quit": self.cmd_quit,
            "exit": self.cmd_quit,
        }

    # ------------------------------------------------------------------ boot
    def start(self):
        """Launch the curses UI."""
        curses.wrapper(self._main)

    def stop(self):
        self.running = False
        if self.auto_agent:
            self.auto_agent.stop()
        if self.critic_agent:
            self.critic_agent.stop()

    # --------------------------------------------------------------- curses
    def _main(self, stdscr):
        self._stdscr = stdscr
        curses.curs_set(1)
        stdscr.nodelay(False)
        stdscr.timeout(100)  # 100 ms refresh

        # Colours
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)    # left header
        curses.init_pair(2, curses.COLOR_CYAN, -1)     # middle header
        curses.init_pair(3, curses.COLOR_YELLOW, -1)   # input prompt
        curses.init_pair(4, curses.COLOR_RED, -1)      # separator
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # right header (critic)

        self.running = True

        # Welcome
        self.left_buf.add(f"  {AGENT_NAME} - Split Screen Mode")
        self.left_buf.add("  Type 'help' for commands.")
        self.left_buf.add("  Right-top:    autonomous agent")
        self.left_buf.add("  Right-bottom: critic agent")
        self.left_buf.add("")

        # Start both agents
        self._launch_auto_agent()
        self._launch_critic_agent()

        # Main loop
        while self.running:
            self._draw(stdscr)
            self._handle_input(stdscr)

        # Cleanup
        if self.auto_agent:
            self.auto_agent.stop()
        if self.critic_agent:
            self.critic_agent.stop()

    def _launch_auto_agent(self):
        """Start the autonomous agent feeding into the right-top pane."""
        self.auto_agent = AutonomousAgent(
            cycle_delay=30,
            on_output=lambda text: self.agent_buf.add(text),
            inbox=self.critic_to_agent,   # receives critic feedback
            outbox=self.agent_to_critic,  # sends output to critic
        )
        self.auto_agent.start()

    def _launch_critic_agent(self):
        """Start the critic agent feeding into the right-bottom pane."""
        self.critic_agent = CriticAgent(
            cycle_delay=5,
            on_output=lambda text: self.critic_buf.add(text),
            inbox=self.agent_to_critic,   # reads primary agent output
            outbox=self.critic_to_agent,  # sends feedback to primary
        )
        self.critic_agent.start()

    # --------------------------------------------------------------- draw
    def _draw(self, stdscr):
        try:
            height, width = stdscr.getmaxyx()
            if height < 8 or width < 60:
                stdscr.clear()
                stdscr.addstr(0, 0, "Terminal too small! Need 60+ cols, 8+ rows.")
                stdscr.refresh()
                return

            # Two columns: left (control) | right (agent top / critic bottom)
            mid_col = width // 2
            left_w = mid_col - 1
            right_w = width - mid_col - 1

            # Right pane split: top half = agent, bottom half = critic
            content_top = 1
            content_bottom = height - 2  # reserve last row for input
            content_h = content_bottom - content_top
            right_top_h = content_h // 2
            right_bot_h = content_h - right_top_h
            right_split_row = content_top + right_top_h  # horizontal divider row

            stdscr.erase()

            # ---- headers ----
            left_title = f" {AGENT_NAME} - Control "

            agent_status = "RUN" if (self.auto_agent and self.auto_agent.is_running) else (
                "PAUSE" if (self.auto_agent and self.auto_agent.is_paused) else "STOP"
            )
            agent_cycle = self.auto_agent.cycle_count if self.auto_agent else 0
            agent_title = f" Agent [{agent_status}] #{agent_cycle} "

            critic_status = "RUN" if (self.critic_agent and self.critic_agent.is_running) else (
                "PAUSE" if (self.critic_agent and self.critic_agent.is_paused) else "STOP"
            )
            critic_cycle = self.critic_agent.cycle_count if self.critic_agent else 0
            critic_title = f" Critic [{critic_status}] #{critic_cycle} "

            # Left header
            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(0, 0, left_title[:left_w].ljust(left_w))
            stdscr.attroff(curses.color_pair(1))

            # Agent header (right-top)
            focus_agent = "*" if self._focused_pane == "agent" else " "
            stdscr.attron(curses.color_pair(2))
            stdscr.addstr(0, mid_col + 1, f"{focus_agent}{agent_title}"[:right_w].ljust(right_w))
            stdscr.attroff(curses.color_pair(2))

            # ---- vertical separator ----
            stdscr.attron(curses.color_pair(4))
            for row in range(height):
                try:
                    stdscr.addch(row, mid_col, curses.ACS_VLINE)
                except curses.error:
                    pass
            stdscr.attroff(curses.color_pair(4))

            # ---- horizontal separator in right pane (between agent & critic) ----
            stdscr.attron(curses.color_pair(4))
            for col in range(mid_col + 1, width):
                try:
                    stdscr.addch(right_split_row, col, curses.ACS_HLINE)
                except curses.error:
                    pass
            # Draw intersection where vertical meets horizontal
            try:
                stdscr.addch(right_split_row, mid_col, curses.ACS_LTEE)
            except curses.error:
                pass
            stdscr.attroff(curses.color_pair(4))

            # Critic header (on the horizontal divider line, right side)
            focus_critic = "*" if self._focused_pane == "critic" else " "
            stdscr.attron(curses.color_pair(5))
            try:
                stdscr.addstr(right_split_row, mid_col + 1, f"{focus_critic}{critic_title}"[:right_w])
            except curses.error:
                pass
            stdscr.attroff(curses.color_pair(5))

            # ---- content areas ----
            # Left pane: full height
            self._draw_pane(stdscr, self.left_buf.get_lines(),
                            content_top, 0, content_h, left_w)
            # Right-top: agent output (with scroll offset & scrollbar)
            self._draw_pane_scrollable(stdscr, self.agent_buf.get_lines(),
                            content_top, mid_col + 1, right_top_h, right_w,
                            self._agent_scroll)
            # Right-bottom: critic output (with scroll offset & scrollbar)
            self._draw_pane_scrollable(stdscr, self.critic_buf.get_lines(),
                            right_split_row + 1, mid_col + 1, right_bot_h - 1, right_w,
                            self._critic_scroll)

            # ---- input line (spans left pane) ----
            prompt = "[You] > "
            input_row = height - 1
            stdscr.attron(curses.color_pair(3))
            try:
                stdscr.addstr(input_row, 0, prompt[:left_w])
            except curses.error:
                pass
            stdscr.attroff(curses.color_pair(3))

            avail = left_w - len(prompt)
            visible = self.input_line[-avail:] if len(self.input_line) > avail else self.input_line
            try:
                stdscr.addstr(input_row, len(prompt), visible)
            except curses.error:
                pass

            cursor_x = min(len(prompt) + len(visible), left_w - 1)
            try:
                stdscr.move(input_row, cursor_x)
            except curses.error:
                pass

            stdscr.refresh()
        except curses.error:
            pass

    def _draw_pane(self, stdscr, lines: list, top: int, left: int,
                   height: int, width: int):
        """Draw wrapped text lines in a pane region, auto-scrolled to bottom."""
        wrapped = []
        for line in lines:
            if not line:
                wrapped.append("")
            else:
                wrapped.extend(textwrap.wrap(line, width) or [""])

        visible = wrapped[-height:] if len(wrapped) > height else wrapped

        for i, line in enumerate(visible):
            row = top + (height - len(visible)) + i
            if row < top or row >= top + height:
                continue
            try:
                stdscr.addnstr(row, left, line, width)
            except curses.error:
                pass

    def _draw_pane_scrollable(self, stdscr, lines: list, top: int, left: int,
                              height: int, width: int, scroll_offset: int):
        """Draw wrapped text with scroll offset and a scrollbar track."""
        # Reserve 1 col for scrollbar
        text_w = max(width - 1, 1)
        sb_col = left + text_w

        # Wrap all lines to text width
        wrapped = []
        for line in lines:
            if not line:
                wrapped.append("")
            else:
                wrapped.extend(textwrap.wrap(line, text_w) or [""])

        total = len(wrapped)

        # Clamp scroll offset
        max_scroll = max(0, total - height)
        offset = min(scroll_offset, max_scroll)

        # Compute visible window
        if total <= height:
            visible = wrapped
        else:
            end = total - offset
            start = max(0, end - height)
            visible = wrapped[start:end]

        # Draw text lines
        for i, line in enumerate(visible):
            row = top + (height - len(visible)) + i
            if row < top or row >= top + height:
                continue
            try:
                stdscr.addnstr(row, left, line, text_w)
            except curses.error:
                pass

        # Draw scrollbar
        if total > height and height > 1:
            # Scrollbar thumb position
            thumb_size = max(1, height * height // total)
            # Position: 0 offset = thumb at bottom, max_scroll offset = thumb at top
            if max_scroll > 0:
                thumb_top = top + int((max_scroll - offset) / max_scroll * (height - thumb_size))
            else:
                thumb_top = top + height - thumb_size

            for row in range(top, top + height):
                ch = curses.ACS_CKBOARD if thumb_top <= row < thumb_top + thumb_size else curses.ACS_VLINE
                try:
                    stdscr.addch(row, sb_col, ch)
                except curses.error:
                    pass
            # Show scroll indicator if not at bottom
            if offset > 0:
                try:
                    stdscr.addch(top + height - 1, sb_col, ord('v'))
                except curses.error:
                    pass

    # --------------------------------------------------------------- input
    def _handle_input(self, stdscr):
        try:
            ch = stdscr.getch()
        except curses.error:
            return

        if ch == -1:
            return

        if ch in (curses.KEY_ENTER, 10, 13):
            self._process_input()
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            self.input_line = self.input_line[:-1]
        elif ch == curses.KEY_UP:
            if self.input_history:
                self.input_hist_idx = max(0, self.input_hist_idx - 1)
                self.input_line = self.input_history[self.input_hist_idx]
        elif ch == curses.KEY_DOWN:
            if self.input_history:
                self.input_hist_idx = min(len(self.input_history), self.input_hist_idx + 1)
                if self.input_hist_idx >= len(self.input_history):
                    self.input_line = ""
                else:
                    self.input_line = self.input_history[self.input_hist_idx]
        elif ch == 9:  # Tab — switch focused right pane
            self._focused_pane = "critic" if self._focused_pane == "agent" else "agent"
        elif ch == curses.KEY_PPAGE:  # Page Up — scroll focused pane up
            if self._focused_pane == "agent":
                self._agent_scroll += 5
            else:
                self._critic_scroll += 5
        elif ch == curses.KEY_NPAGE:  # Page Down — scroll focused pane down
            if self._focused_pane == "agent":
                self._agent_scroll = max(0, self._agent_scroll - 5)
            else:
                self._critic_scroll = max(0, self._critic_scroll - 5)
        elif ch == curses.KEY_END:  # End — snap to bottom (auto-follow)
            if self._focused_pane == "agent":
                self._agent_scroll = 0
            else:
                self._critic_scroll = 0
        elif ch == curses.KEY_HOME:  # Home — scroll to top
            if self._focused_pane == "agent":
                self._agent_scroll = MAX_BUFFER_LINES
            else:
                self._critic_scroll = MAX_BUFFER_LINES
        elif ch == 3:  # Ctrl+C
            self.cmd_quit("")
        elif 32 <= ch <= 126:
            self.input_line += chr(ch)

    def _process_input(self):
        user_input = self.input_line.strip()
        self.input_line = ""

        if not user_input:
            return

        self.input_history.append(user_input)
        self.input_hist_idx = len(self.input_history)

        self.left_buf.add(f"[You] > {user_input}")

        parts = user_input.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in self.commands:
            self.commands[cmd](args)
        else:
            self._chat(user_input)

    # ---------------------------------------------------------- helpers
    def _resolve_target(self, args: str):
        """Parse 'agent|critic [rest]' from args. Returns (target, remaining_args).
        target is 'agent', 'critic', or 'both'. Defaults to 'both' if not specified."""
        parts = args.strip().split(maxsplit=1)
        if parts and parts[0].lower() in ("agent", "critic", "both"):
            target = parts[0].lower()
            rest = parts[1] if len(parts) > 1 else ""
            return target, rest
        return "both", args

    # ------------------------------------------------------------- commands
    def _out(self, text: str):
        """Write to the left pane."""
        self.left_buf.add(text)

    def _chat(self, message: str):
        self._out("[CrapBot] Thinking...")
        def _bg():
            response = self.ai.chat(message)
            self._out(f"[CrapBot] {response}")
        threading.Thread(target=_bg, daemon=True).start()

    def cmd_help(self, args: str):
        tools_status = "ON" if self.ai.tools_enabled else "OFF"
        self._out(f"""
Commands:
  help              - Show this help
  do <task>         - Execute task autonomously
  chat <msg>        - Chat with AI
  search <query>    - Web search
  research <problem> - Deep research with planning & review

Agent Control (use: <cmd> [agent|critic|both]):
  stop [target]     - Stop agent/critic/both
  start [target]    - Start agent/critic/both
  pause [target]    - Pause agent/critic/both
  resume [target]   - Resume agent/critic/both
  fresh             - Clear session & restart both agents
  agents            - Show status of both agents
  instruct <target> <text> - Change instructions (single-line)
  topic             - Set topic with multi-line editor

Task Management:
  task <desc>       - Background task
  tasks             - List tasks
  status <id>       - Task status
  cancel <id>       - Cancel task
  schedule          - List/add scheduled tasks

Settings:
  model <name>      - Switch model ({self.ai.current_model})
  models            - List models
  tools [on|off]    - Toggle tools ({tools_status})
  reset             - Reset chat history
  clear [target]    - Clear pane (left/agent/critic/all)
  quit/exit         - Exit""")

    def cmd_agents_status(self, args: str):
        """Show status of both agents."""
        if self.auto_agent:
            a_status = "RUNNING" if self.auto_agent.is_running else (
                "PAUSED" if self.auto_agent.is_paused else "STOPPED")
            self._out(f"  Agent:  {a_status} | cycles: {self.auto_agent.cycle_count}")
        else:
            self._out("  Agent:  NOT CREATED")
        if self.critic_agent:
            c_status = "RUNNING" if self.critic_agent.is_running else (
                "PAUSED" if self.critic_agent.is_paused else "STOPPED")
            self._out(f"  Critic: {c_status} | reviews: {self.critic_agent.cycle_count}")
        else:
            self._out("  Critic: NOT CREATED")

    def cmd_stop_agent(self, args: str):
        target, _ = self._resolve_target(args)
        if target in ("agent", "both"):
            if self.auto_agent:
                self.auto_agent.stop()
                self._out("[System] Agent stopped.")
            else:
                self._out("[System] No agent running.")
        if target in ("critic", "both"):
            if self.critic_agent:
                self.critic_agent.stop()
                self._out("[System] Critic stopped.")
            else:
                self._out("[System] No critic running.")

    def cmd_start_agent(self, args: str):
        target, _ = self._resolve_target(args)
        if target in ("agent", "both"):
            if self.auto_agent and self.auto_agent.is_running:
                self._out("[System] Agent already running.")
            else:
                self.agent_buf.clear()
                self._launch_auto_agent()
                self._out("[System] Agent started.")
        if target in ("critic", "both"):
            if self.critic_agent and self.critic_agent.is_running:
                self._out("[System] Critic already running.")
            else:
                self.critic_buf.clear()
                self._launch_critic_agent()
                self._out("[System] Critic started.")

    def cmd_pause_agent(self, args: str):
        target, _ = self._resolve_target(args)
        if target in ("agent", "both"):
            if self.auto_agent:
                self.auto_agent.pause()
                self._out("[System] Agent paused.")
            else:
                self._out("[System] No agent running.")
        if target in ("critic", "both"):
            if self.critic_agent:
                self.critic_agent.pause()
                self._out("[System] Critic paused.")
            else:
                self._out("[System] No critic running.")

    def cmd_resume_agent(self, args: str):
        target, _ = self._resolve_target(args)
        if target in ("agent", "both"):
            if self.auto_agent:
                self.auto_agent.resume()
                self._out("[System] Agent resumed.")
            else:
                self._out("[System] No agent running.")
        if target in ("critic", "both"):
            if self.critic_agent:
                self.critic_agent.resume()
                self._out("[System] Critic resumed.")
            else:
                self._out("[System] No critic running.")

    def cmd_instruct_agent(self, args: str):
        target, rest = self._resolve_target(args)
        if not rest:
            # Show current instructions
            if target in ("agent", "both") and self.auto_agent:
                self._out(f"[Agent prompt] {self.auto_agent.get_instructions()[:200]}...")
            if target in ("critic", "both") and self.critic_agent:
                self._out(f"[Critic prompt] {self.critic_agent.get_instructions()[:200]}...")
            return
        if target in ("agent", "both"):
            if self.auto_agent:
                self.auto_agent.update_instructions(rest)
                self._out("[System] Agent instructions updated.")
        if target in ("critic", "both"):
            if self.critic_agent:
                self.critic_agent.update_instructions(rest)
                self._out("[System] Critic instructions updated.")

    def cmd_topic(self, args: str):
        """Provide a topic or multi-line text to the agent/critic session.
        
        Opens an editor for multi-line input. The topic will be injected as context
        into the agents' instructions to guide their discussion.
        """
        self._out("[System] Opening editor for multi-line topic input...")
        self._out("[System] The terminal will be suspended. Save and close the editor when done.")
        
        # We need to suspend curses temporarily to use the editor
        curses.def_prog_mode()  # Save current curses state
        curses.endwin()  # Exit curses mode temporarily
        
        try:
            topic_text = get_multiline_input("")
            
            if not topic_text:
                self._out("[System] No topic provided. Cancelled.")
                return
                
            # Restore curses
            curses.reset_prog_mode()
            self._stdscr.refresh()
            
            # Show the topic
            self._out(f"[System] Topic received ({len(topic_text)} characters):")
            preview = topic_text[:200] + ("..." if len(topic_text) > 200 else "")
            self._out(f"  {preview}")
            
            # Update both agents with topic context
            topic_instruction = f"Focus your discussion on this topic:\n\n{topic_text}\n\n"
            
            if self.auto_agent:
                current_prompt = self.auto_agent.get_instructions()
                # Prepend topic to existing instructions
                new_prompt = topic_instruction + current_prompt
                self.auto_agent.update_instructions(new_prompt)
                self._out("[System] Topic added to Agent instructions.")
                
            if self.critic_agent:
                current_prompt = self.critic_agent.get_instructions()
                # Prepend topic to existing instructions
                new_prompt = topic_instruction + current_prompt
                self.critic_agent.update_instructions(new_prompt)
                self._out("[System] Topic added to Critic instructions.")
                
        except Exception as e:
            # Restore curses even on error
            curses.reset_prog_mode()
            self._stdscr.refresh()
            self._out(f"[Error] Failed to get topic: {e}")

    def cmd_clear(self, args: str):
        target = args.strip().lower() if args else "left"
        if target in ("left", "control"):
            self.left_buf.clear()
        elif target == "agent":
            self.agent_buf.clear()
        elif target == "critic":
            self.critic_buf.clear()
        elif target == "all":
            self.left_buf.clear()
            self.agent_buf.clear()
            self.critic_buf.clear()
        else:
            self.left_buf.clear()

    def cmd_search(self, args: str):
        if not args:
            self._out("[Error] Provide a search query.")
            return
        self._out("[CrapBot] Searching...")
        def _bg():
            response = self.ai.search(args)
            self._out(f"[CrapBot] {response}")
        threading.Thread(target=_bg, daemon=True).start()

    def cmd_model(self, args: str):
        if not args:
            self._out(f"[System] Model: {self.ai.current_model}")
            self._out(f"[System] Available: {', '.join(self.ai.list_models())}")
            return
        result = self.ai.switch_model(args.strip())
        self._out(f"[System] {result}")

    def cmd_models(self, args: str):
        current = self.ai.current_model
        self._out("Available Models:")
        for m in self.ai.list_models():
            marker = " (current)" if m == current else ""
            self._out(f"  - {m}{marker}")

    def cmd_tools(self, args: str):
        if not args:
            status = "enabled" if self.ai.tools_enabled else "disabled"
            self._out(f"[System] Tools: {status}")
            return
        arg = args.strip().lower()
        if arg == "on":
            self.ai.toggle_tools(True)
            self._out("[System] Tools enabled")
        elif arg == "off":
            self.ai.toggle_tools(False)
            self._out("[System] Tools disabled")
        else:
            self._out("[Error] Use 'tools on' or 'tools off'")

    def cmd_chat(self, args: str):
        if not args:
            self._out("[Error] Provide a message.")
            return
        self._chat(args)

    def cmd_reset(self, args: str):
        self.ai.reset_conversation()
        self._out("[System] Conversation history cleared.")

    def cmd_fresh_restart(self, args: str):
        """Clear last session data and restart both agents fresh."""
        import os
        self._out("[System] Stopping both agents...")
        if self.auto_agent:
            # Stop without saving session (we want to discard it)
            self.auto_agent._running = False
            if self.auto_agent._thread:
                self.auto_agent._thread.join(timeout=5)
                self.auto_agent._thread = None
        if self.critic_agent:
            self.critic_agent.stop()

        # Delete last session file
        if os.path.exists(_SESSION_FILE):
            os.remove(_SESSION_FILE)
            self._out("[System] Last session data cleared.")
        else:
            self._out("[System] No session data to clear.")

        # Clear pane buffers and scroll state
        self.agent_buf.clear()
        self.critic_buf.clear()
        self._agent_scroll = 0
        self._critic_scroll = 0

        # Restart both agents (they will load instructions from instructions.json)
        self._launch_auto_agent()
        self._launch_critic_agent()
        self._out("[System] Both agents restarted fresh with current instructions.")

    def cmd_task(self, args: str):
        if not args:
            self._out("[Error] Provide a task description.")
            return
        def run_ai_task(prompt):
            ai = get_ai_client()
            return ai.chat(prompt, system_prompt="You are executing a background task. Complete it thoroughly.")
        task_id = self.tasks.add_task(name=f"AI Task: {args[:30]}...", func=run_ai_task, args=(args,))
        self._out(f"[System] Created task: {task_id}")

    def cmd_list_tasks(self, args: str):
        tasks = self.tasks.list_tasks()
        if not tasks:
            self._out("[System] No tasks.")
            return
        self._out("Background Tasks:")
        for t in tasks:
            recurring = " (recurring)" if t['is_recurring'] else ""
            self._out(f"  {t['id']}: {t['name']} - {t['status']}{recurring}")

    def cmd_status(self, args: str):
        if not args:
            self._out("[Error] Provide a task ID.")
            return
        status = self.tasks.get_task_status(args.strip())
        if "error" in status:
            self._out(f"[Error] {status['error']}")
            return
        self._out(f"Task: {status['name']} | Status: {status['status']} | Runs: {status['run_count']}")

    def cmd_cancel(self, args: str):
        if not args:
            self._out("[Error] Provide a task ID.")
            return
        if self.tasks.cancel_task(args.strip()):
            self._out(f"[System] Task {args} cancelled.")
        else:
            self._out(f"[Error] Task not found: {args}")

    def cmd_history(self, args: str):
        if not args:
            self._out("[Error] Provide a task ID.")
            return
        history = self.tasks.get_task_history(task_id=args.strip())
        if not history:
            self._out("[System] No history.")
            return
        for h in history[-5:]:
            status = "OK" if not h.get('error') else "FAIL"
            self._out(f"  [{status}] Run #{h.get('run', '?')}: {str(h.get('result', ''))[:80]}...")

    def cmd_outputs(self, args: str):
        if not args:
            folders = list_task_folders()
            if not folders:
                self._out("[System] No outputs.")
                return
            for f in folders:
                self._out(f"  {f['name']}: {f['output_count']} outputs")
            return
        outputs = self.tasks.get_task_outputs(task_id=args.strip(), limit=5)
        if not outputs:
            self._out(f"[System] No outputs for: {args}")
            return
        for o in outputs:
            status = "OK" if o.get('success') else "FAIL"
            self._out(f"  [{status}] Run #{o.get('run_number', '?')}: {str(o.get('result', ''))[:80]}...")

    def cmd_schedule(self, args: str):
        if not args:
            tasks = list_configured_tasks()
            self._out("Scheduled Tasks:")
            for t in tasks:
                s = "ON" if t.get('enabled') else "OFF"
                self._out(f"  [{s}] {t['name']} ({t['type']}) every {t.get('interval', 0)}s")
            return
        parts = args.split(maxsplit=2)
        if len(parts) < 3:
            self._out("[Error] Usage: schedule <name> <seconds> <prompt>")
            return
        name, interval_str, prompt = parts
        try:
            interval = int(interval_str)
        except ValueError:
            self._out("[Error] Interval must be a number.")
            return
        if add_scheduled_task(name, prompt, interval, use_history=True):
            self._out(f"[System] Scheduled '{name}' every {interval}s")
        else:
            self._out(f"[Error] Task '{name}' already exists.")

    def cmd_do(self, args: str):
        if not args:
            self._out("[Error] Provide a task description.")
            return
        self._out("[CrapBot] Working on it...")
        def _bg():
            response = self.ai.chat(
                f"Task: {args}\n\nComplete this task. If it requires code, write and execute it.",
            )
            self._out(f"[CrapBot] {response}")
        threading.Thread(target=_bg, daemon=True).start()
    
    def cmd_research(self, args: str):
        """Run deep research with autonomous planning and critical review."""
        if not args:
            self._out("[Error] Please provide a research problem.")
            return
        
        self._out("[Deep Research] Starting research session...")
        self._out("[Deep Research] This involves planning, search, analysis, and review.")
        
        def _bg():
            try:
                result = run_deep_research(problem=args, on_output=self._out)
                
                # Display summary
                self._out("\n" + "="*60)
                self._out("RESEARCH SUMMARY")
                self._out("="*60)
                self._out(f"Attempts: {len(result['attempts'])}")
                self._out(f"Final Score: {result['final_score']}/10")
                self._out(f"Status: {'✓ Accepted' if result['final_accepted'] else '✗ Needs Work'}")
                
                # Show final answer
                last_attempt = result['attempts'][-1]
                if 'research' in last_attempt and 'final_answer' in last_attempt['research']:
                    self._out("\nFINAL ANSWER:")
                    self._out("-" * 60)
                    self._out(last_attempt['research']['final_answer'])
                
            except Exception as e:
                self._out(f"[Error] Research failed: {e}")
        
        threading.Thread(target=_bg, daemon=True).start()

    def cmd_quit(self, args: str):
        self._out("[System] Shutting down...")
        self.running = False
