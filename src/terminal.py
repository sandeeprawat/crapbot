"""Terminal interface for the AI Agent."""
import sys
import threading
import json
from ai_client import get_ai_client
from task_manager import get_task_manager, list_task_folders
from autonomous_tasks import add_scheduled_task, remove_scheduled_task, list_configured_tasks
from tools import create_system_change_approval
from deep_research_agent import run_deep_research


SYSTEM_FIX_PLANNER_PROMPT = """You are a Windows troubleshooting planner.
Analyze the user's issue and propose a safe, step-by-step fix plan.
Return ONLY valid JSON with this schema:
{
    "summary": "short description",
    "diagnostics": ["PowerShell command", ...],
    "fixes": [
        {
            "title": "short name",
            "risk": "low|medium|high",
            "requires_admin": true|false,
            "commands": ["PowerShell command", ...],
            "rollback": "optional rollback steps"
        }
    ]
}
Rules:
- Keep commands Windows PowerShell compatible.
- Prefer diagnostics first, fixes second.
- Avoid destructive actions; if unavoidable, mark risk=high.
"""


SYSTEM_FIX_EXECUTOR_PROMPT = """You are executing an approved Windows fix plan.
You must:
- Use ONLY the run_powershell_guarded tool for any command execution.
- Use the provided approval_id for every command.
- Run diagnostics first, then fixes in order.
- Stop if a command fails and report the error.
- Summarize results and next steps.
"""


class Terminal:
    """Interactive terminal for agent commands."""
    
    def __init__(self):
        self.ai = get_ai_client()
        self.tasks = get_task_manager()
        self.running = False
        self.commands = {
            "help": self.cmd_help,
            "chat": self.cmd_chat,
            "search": self.cmd_search,
            "model": self.cmd_model,
            "models": self.cmd_models,
            "tools": self.cmd_tools,
            "reset": self.cmd_reset,
            "fix": self.cmd_fix,
            "task": self.cmd_task,
            "tasks": self.cmd_list_tasks,
            "schedule": self.cmd_schedule,
            "status": self.cmd_status,
            "history": self.cmd_history,
            "outputs": self.cmd_outputs,
            "cancel": self.cmd_cancel,
            "do": self.cmd_do,
            "research": self.cmd_research,
            "quit": self.cmd_quit,
            "exit": self.cmd_quit,
        }
        
    def start(self):
        """Start the terminal."""
        self.running = True
        self.print_banner()
        self._run_loop()
        
    def stop(self):
        """Stop the terminal."""
        self.running = False
        
    def print_banner(self):
        """Print welcome banner."""
        tools_status = "ON" if self.ai.tools_enabled else "OFF"
        print("\n" + "="*60)
        print("  CRAPBOT - AI Agent Terminal")
        print(f"  Model: {self.ai.current_model} | Tools: {tools_status}")
        print("="*60 + "\n")
        
    def _run_loop(self):
        """Main terminal loop."""
        while self.running:
            try:
                user_input = input("\n[You] > ").strip()
                
                if not user_input:
                    continue
                    
                # Check if it's a command
                parts = user_input.split(maxsplit=1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                
                if cmd in self.commands:
                    self.commands[cmd](args)
                else:
                    # Treat as chat message
                    self._chat(user_input)
                    
            except KeyboardInterrupt:
                print("\n\nUse 'quit' to exit.")
            except EOFError:
                self.cmd_quit("")
            except Exception as e:
                print(f"[Error] {e}")
                
    def _chat(self, message: str):
        """Send chat message to AI."""
        print("\n[CrapBot] Thinking...")
        response = self.ai.chat(message)
        print(f"\n[CrapBot] {response}")
        
    def cmd_help(self, args: str):
        """Show help."""
        tools_status = "ON" if self.ai.tools_enabled else "OFF"
        help_text = f"""
Available Commands:
  help              - Show this help
  do <task>         - Execute task autonomously (writes & runs code if needed)
    fix <issue>       - Diagnose and fix a Windows issue (asks before changes)
  chat <message>    - Chat with the AI (or just type your message)
  search <query>    - Search the web
  research <problem> - Run deep research with autonomous planning and review
  
Task Management:
  task <desc>       - Create a one-time background task
  schedule          - List scheduled tasks from config
  schedule <name> <seconds> <prompt>  - Add a recurring scheduled task
  tasks             - List all running tasks
  status <id>       - Get status of a task
  history <id>      - View execution history of a task
  outputs [id]      - View saved task outputs (files)
  cancel <id>       - Cancel a task

Settings:
  model <name>      - Switch AI model (current: {self.ai.current_model})
  models            - List available models  
  tools [on|off]    - Toggle tool calling (current: {tools_status})
  reset             - Reset conversation history
  quit/exit         - Exit the terminal

Task Output Storage:
  All task outputs are saved to: task_data/<task_name>/
  Tasks can access their previous outputs via 'use_history' option.

Autonomous Execution:
  Use 'do <task>' for complex tasks - the agent will write and execute
  code (Python, JS, PowerShell) autonomously to complete the task.

Deep Research:
  Use 'research <problem>' for thorough autonomous research with:
  - Adaptive planning based on problem type
  - Web search with Bing grounding
  - Code analysis and data gathering
  - Critical review and iteration
  - Researcher-reviewer discussion for quality
        """
        print(help_text)
    
    def cmd_search(self, args: str):
        """Search the web."""
        if not args:
            print("[Error] Please provide a search query.")
            return
        print("\n[CrapBot] Searching...")
        response = self.ai.search(args)
        print(f"\n[CrapBot] {response}")
        
    def cmd_model(self, args: str):
        """Switch model."""
        if not args:
            print(f"[System] Current model: {self.ai.current_model}")
            print(f"[System] Available: {', '.join(self.ai.list_models())}")
            return
        result = self.ai.switch_model(args.strip())
        print(f"[System] {result}")
        
    def cmd_models(self, args: str):
        """List models."""
        models = self.ai.list_models()
        current = self.ai.current_model
        print("\nAvailable Models:")
        for m in models:
            marker = " (current)" if m == current else ""
            print(f"  - {m}{marker}")
    
    def cmd_tools(self, args: str):
        """Toggle or list tools."""
        if not args:
            status = "enabled" if self.ai.tools_enabled else "disabled"
            print(f"[System] Tools are {status}")
            print(f"[System] Available: {', '.join(self.ai.get_available_tools())}")
            return
        
        arg = args.strip().lower()
        if arg == "on":
            self.ai.toggle_tools(True)
            print("[System] Tools enabled")
        elif arg == "off":
            self.ai.toggle_tools(False)
            print("[System] Tools disabled")
        else:
            print("[Error] Use 'tools on' or 'tools off'")
        
    def cmd_chat(self, args: str):
        """Explicit chat command."""
        if not args:
            print("[Error] Please provide a message.")
            return
        self._chat(args)
        
    def cmd_reset(self, args: str):
        """Reset conversation."""
        self.ai.reset_conversation()
        print("[System] Conversation history cleared.")
        
    def cmd_task(self, args: str):
        """Create a background task."""
        if not args:
            print("[Error] Please provide a task description.")
            return
            
        def run_ai_task(prompt):
            ai = get_ai_client()
            return ai.chat(prompt, system_prompt="You are executing a background task. Complete it thoroughly and return the result.")
            
        task_id = self.tasks.add_task(
            name=f"AI Task: {args[:30]}...",
            func=run_ai_task,
            args=(args,)
        )
        print(f"[System] Created background task: {task_id}")
        print("[System] Use 'status {task_id}' to check progress.")
        
    def cmd_list_tasks(self, args: str):
        """List all tasks."""
        tasks = self.tasks.list_tasks()
        if not tasks:
            print("[System] No tasks.")
            return
            
        print("\nBackground Tasks:")
        print("-" * 50)
        for t in tasks:
            status = t['status']
            recurring = " (recurring)" if t['is_recurring'] else ""
            print(f"  {t['id']}: {t['name']} - {status}{recurring}")
        print("-" * 50)
        
    def cmd_status(self, args: str):
        """Get task status."""
        if not args:
            print("[Error] Please provide a task ID.")
            return
            
        status = self.tasks.get_task_status(args.strip())
        if "error" in status:
            print(f"[Error] {status['error']}")
            return
            
        print(f"\nTask: {status['name']}")
        print(f"  Status: {status['status']}")
        print(f"  Run count: {status['run_count']}")
        if status['last_run']:
            print(f"  Last run: {status['last_run']}")
        if status['result']:
            result_preview = str(status['result'])[:500]
            print(f"  Result: {result_preview}...")
        if status['error']:
            print(f"  Error: {status['error']}")
            
    def cmd_cancel(self, args: str):
        """Cancel a task."""
        if not args:
            print("[Error] Please provide a task ID.")
            return
            
        if self.tasks.cancel_task(args.strip()):
            print(f"[System] Task {args} cancelled.")
        else:
            print(f"[Error] Task not found: {args}")
    
    def cmd_history(self, args: str):
        """View task execution history."""
        if not args:
            print("[Error] Please provide a task ID.")
            return
        
        history = self.tasks.get_task_history(task_id=args.strip())
        if not history:
            print("[System] No history found for this task.")
            return
        
        print(f"\nExecution History (last {len(history)} runs):")
        print("-" * 50)
        for h in history[-10:]:
            status = "✓" if not h.get('error') else "✗"
            result_preview = str(h.get('result', ''))[:100] if h.get('result') else h.get('error', '')[:100]
            print(f"  {status} Run #{h.get('run', '?')} [{h.get('timestamp', '')}]")
            print(f"    {result_preview}...")
        print("-" * 50)
    
    def cmd_outputs(self, args: str):
        """View saved task outputs."""
        if not args:
            # List all task folders
            folders = list_task_folders()
            if not folders:
                print("[System] No task outputs found.")
                return
            
            print("\nTask Output Folders:")
            print("-" * 50)
            for f in folders:
                print(f"  {f['name']}: {f['output_count']} outputs")
            print("-" * 50)
            return
        
        # Show outputs for specific task
        outputs = self.tasks.get_task_outputs(task_id=args.strip(), limit=5)
        if not outputs:
            print(f"[System] No outputs found for task: {args}")
            return
        
        print(f"\nRecent Outputs:")
        print("-" * 50)
        for o in outputs:
            status = "✓" if o.get('success') else "✗"
            result = str(o.get('result', o.get('error', '')))[:150]
            print(f"  {status} Run #{o.get('run_number', '?')} [{o.get('timestamp', '')}]")
            print(f"    {result}...")
        print("-" * 50)
    
    def cmd_schedule(self, args: str):
        """Schedule a recurring task."""
        if not args:
            # List configured scheduled tasks
            tasks = list_configured_tasks()
            print("\nScheduled Tasks (from config):")
            print("-" * 60)
            for t in tasks:
                status = "✓" if t.get('enabled') else "✗"
                interval = t.get('interval', 0)
                history = " [uses history]" if t.get('use_history') else ""
                print(f"  {status} {t['name']} ({t['type']}) - every {interval}s{history}")
            print("-" * 60)
            print("Use: schedule <name> <interval_seconds> <prompt>")
            return
        
        # Parse: schedule <name> <interval> <prompt>
        parts = args.split(maxsplit=2)
        if len(parts) < 3:
            print("[Error] Usage: schedule <name> <interval_seconds> <prompt>")
            print("  Example: schedule DailyReport 3600 Generate a daily summary report")
            return
        
        name, interval_str, prompt = parts
        try:
            interval = int(interval_str)
        except ValueError:
            print("[Error] Interval must be a number of seconds.")
            return
        
        if add_scheduled_task(name, prompt, interval, use_history=True):
            print(f"[System] Scheduled task '{name}' added (runs every {interval}s)")
            print("[System] Restart the agent to activate, or it will be active on next start.")
        else:
            print(f"[Error] Task '{name}' already exists.")
    
    def cmd_do(self, args: str):
        """Execute a task autonomously - agent will write and run code if needed."""
        if not args:
            print("[Error] Please provide a task description.")
            return
        
        print("\n[CrapBot] Working on it (may write and execute code)...")
        response = self.ai.chat(
            f"Task: {args}\n\nComplete this task. If it requires computation, data processing, or any programming, write and execute the necessary code. Show the actual results.",
        )
        print(f"\n[CrapBot] {response}")
    
    def cmd_research(self, args: str):
        """Run deep research with autonomous planning and critical review."""
        if not args:
            print("[Error] Please provide a research problem.")
            print("\nExamples:")
            print("  research Identify stocks that could make good returns in next few months")
            print("  research Come up with a novel philosophical concept")
            return
        
        print("\n[Deep Research] Starting autonomous research session...")
        print("[Deep Research] This will involve planning, web search, analysis, and critical review.")
        print("[Deep Research] The process may take several minutes.\n")
        
        try:
            # Run the deep research
            result = run_deep_research(problem=args, on_output=print)
            
            # Display summary
            print("\n" + "="*80)
            print("RESEARCH SUMMARY")
            print("="*80)
            print(f"Problem: {result['problem']}")
            print(f"Attempts: {len(result['attempts'])}")
            print(f"Final Score: {result['final_score']}/10")
            print(f"Status: {'✓ Accepted' if result['final_accepted'] else '✗ Needs Improvement'}")
            
            # Show final answer from last attempt
            last_attempt = result['attempts'][-1]
            if 'research' in last_attempt and 'final_answer' in last_attempt['research']:
                print("\nFINAL ANSWER:")
                print("-" * 80)
                print(last_attempt['research']['final_answer'])
            
            print("\n" + "="*80)
            
        except Exception as e:
            print(f"\n[Error] Research failed: {e}")
            import traceback
            traceback.print_exc()

    def cmd_fix(self, args: str):
        """Diagnose and fix a Windows issue with explicit approval."""
        if not args:
            print("[Error] Please describe the issue to fix.")
            return

        print("\n[CrapBot] Planning a fix... (no changes yet)")
        plan_text = self.ai.chat(
            args,
            system_prompt=SYSTEM_FIX_PLANNER_PROMPT,
            use_tools=False,
        )

        try:
            plan = json.loads(plan_text)
        except json.JSONDecodeError:
            print("[Error] Planner did not return valid JSON. Showing raw response:\n")
            print(plan_text)
            return

        summary = plan.get("summary", "(no summary)")
        diagnostics = plan.get("diagnostics", [])
        fixes = plan.get("fixes", [])

        print("\nProposed plan:")
        print(f"  Summary: {summary}")
        if diagnostics:
            print("  Diagnostics:")
            for cmd in diagnostics:
                print(f"    - {cmd}")
        if fixes:
            print("  Fixes:")
            for i, fix in enumerate(fixes, 1):
                title = fix.get("title", f"Fix {i}")
                risk = fix.get("risk", "unknown")
                admin = "admin" if fix.get("requires_admin") else "user"
                print(f"    {i}. {title} (risk: {risk}, {admin})")
                for cmd in fix.get("commands", []):
                    print(f"       - {cmd}")
                if fix.get("rollback"):
                    print(f"       rollback: {fix['rollback']}")

        confirm = input("\nRun this plan now? (y/N): ").strip().lower()
        if confirm != "y":
            print("[System] Cancelled. No changes made.")
            return

        approval_id = create_system_change_approval(
            reason=f"Fix issue: {args}",
            duration_seconds=900,
            approved_by="terminal",
        )

        print("\n[CrapBot] Executing plan with approval...\n")
        executor_input = json.dumps({
            "issue": args,
            "approval_id": approval_id,
            "plan": plan,
        })

        response = self.ai.chat(
            executor_input,
            system_prompt=SYSTEM_FIX_EXECUTOR_PROMPT,
            use_tools=True,
            tool_allowlist=["run_powershell_guarded"],
        )
        print(f"\n[CrapBot] {response}")
            
    def cmd_quit(self, args: str):
        """Exit the terminal."""
        print("\n[System] Shutting down...")
        self.running = False
