"""Main AI Agent entry point."""
import signal
import sys
import time
from task_manager import get_task_manager, list_task_folders
from terminal import Terminal
from split_terminal import SplitTerminal
from autonomous_tasks import get_configured_tasks
from config import AGENT_NAME


class Agent:
    """The main AI Agent that runs forever."""
    
    def __init__(self, split_screen: bool = True):
        self.split_screen = split_screen
        self.terminal = None
        self.task_manager = get_task_manager()
        self.running = False
        
    def start(self):
        """Start the agent."""
        print(f"\n{'='*60}")
        print(f"  {AGENT_NAME} - Autonomous AI Agent")
        print(f"  Starting up...")
        print(f"{'='*60}\n")
        
        self.running = True
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Start the task manager
        self.task_manager.start()
        
        # Register tasks from configuration
        self._register_configured_tasks()
        
        print("[Agent] Background task manager started")
        print("[Agent] Tasks loaded from configuration")
        print("[Agent] Starting terminal interface...\n")
        
        # Start the terminal (this blocks)
        try:
            if self.split_screen:
                self.terminal = SplitTerminal()
            else:
                self.terminal = Terminal()
            self.terminal.start()
        except Exception as e:
            print(f"[Agent] Terminal error: {e}")
        finally:
            self.stop()
            
    def stop(self):
        """Stop the agent."""
        if not self.running:
            return
            
        self.running = False
        print("\n[Agent] Shutting down...")
        
        if self.terminal:
            self.terminal.stop()
        self.task_manager.stop()
        
        print("[Agent] Goodbye!\n")
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\n[Agent] Received shutdown signal...")
        self.stop()
        sys.exit(0)
        
    def _register_configured_tasks(self):
        """Register tasks from configuration file."""
        tasks = get_configured_tasks()
        for task_def in tasks:
            task_id = self.task_manager.add_task(
                name=task_def["name"],
                func=task_def["func"],
                interval=task_def.get("interval"),
                use_history=task_def.get("use_history", False),
                max_history=task_def.get("max_history", 10),
                parallel=True  # All scheduled tasks run in parallel
            )
            print(f"[Agent] Registered: {task_def['name']} ({task_id}) - interval: {task_def.get('interval', 'one-time')}s")


def main():
    """Main entry point."""
    split = "--classic" not in sys.argv
    agent = Agent(split_screen=split)
    agent.start()


if __name__ == "__main__":
    main()
