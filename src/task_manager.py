"""Background task manager for autonomous operations with history and parallel execution."""
import threading
import queue
import time
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


# Task storage paths
TASK_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "task_data")
TASK_HISTORY_FILE = os.path.join(TASK_BASE_DIR, "task_history.json")

# Ensure base directory exists
os.makedirs(TASK_BASE_DIR, exist_ok=True)


def get_task_folder(task_name: str) -> str:
    """Get or create a folder for a specific task."""
    # Sanitize task name for folder
    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in task_name)
    safe_name = safe_name.strip().replace(' ', '_')[:50]
    folder = os.path.join(TASK_BASE_DIR, safe_name)
    os.makedirs(folder, exist_ok=True)
    return folder


MAX_TASK_OUTPUTS = 100  # Maximum number of output files per task


def cleanup_old_outputs(folder: str, max_outputs: int = MAX_TASK_OUTPUTS):
    """Remove oldest output files if count exceeds max_outputs."""
    try:
        files = [f for f in os.listdir(folder) if f.endswith('.json')]
        if len(files) > max_outputs:
            # Sort by modification time, oldest first
            files_with_time = [(f, os.path.getmtime(os.path.join(folder, f))) for f in files]
            files_with_time.sort(key=lambda x: x[1])
            # Remove oldest files
            to_remove = len(files) - max_outputs
            for filename, _ in files_with_time[:to_remove]:
                os.remove(os.path.join(folder, filename))
    except Exception as e:
        print(f"[TaskManager] Could not cleanup outputs: {e}")


def save_task_output(task_name: str, run_number: int, result: Any, error: str = None) -> str:
    """Save task output to a file in the task's folder. Returns the file path."""
    folder = get_task_folder(task_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"run_{run_number:04d}_{timestamp}.json"
    filepath = os.path.join(folder, filename)
    
    output_data = {
        "task_name": task_name,
        "run_number": run_number,
        "timestamp": datetime.now().isoformat(),
        "success": error is None,
        "result": result,
        "error": error
    }
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, default=str)
        # Cleanup old outputs to stay within limit
        cleanup_old_outputs(folder)
        return filepath
    except Exception as e:
        print(f"[TaskManager] Could not save output: {e}")
        return None


def load_task_outputs(task_name: str, limit: int = 10) -> List[Dict]:
    """Load previous outputs for a task."""
    folder = get_task_folder(task_name)
    outputs = []
    
    try:
        files = sorted([f for f in os.listdir(folder) if f.endswith('.json')], reverse=True)
        for filename in files[:limit]:
            filepath = os.path.join(folder, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                outputs.append(json.load(f))
    except Exception as e:
        print(f"[TaskManager] Could not load outputs: {e}")
    
    return outputs


def get_latest_task_output(task_name: str) -> Optional[Dict]:
    """Get the most recent output for a task."""
    outputs = load_task_outputs(task_name, limit=1)
    return outputs[0] if outputs else None


def list_task_folders() -> List[Dict]:
    """List all task folders with stats."""
    folders = []
    try:
        for name in os.listdir(TASK_BASE_DIR):
            folder_path = os.path.join(TASK_BASE_DIR, name)
            if os.path.isdir(folder_path) and name != "__pycache__":
                files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
                folders.append({
                    "name": name,
                    "path": folder_path,
                    "output_count": len(files),
                    "latest": max([os.path.getmtime(os.path.join(folder_path, f)) for f in files]) if files else None
                })
    except Exception as e:
        print(f"[TaskManager] Could not list folders: {e}")
    
    return folders


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Stores a single task execution result."""
    timestamp: str
    result: Any
    error: Optional[str] = None
    run_number: int = 0


@dataclass
class Task:
    id: str
    name: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    interval: int = None  # None = one-time, otherwise repeat every N seconds
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = None
    last_run: datetime = None
    run_count: int = 0
    history: List[TaskResult] = field(default_factory=list)
    max_history: int = 10
    use_history: bool = False
    parallel: bool = True  # Whether task can run in parallel with others
    future: Future = None  # Track running future for parallel tasks


class TaskManager:
    """Manages background autonomous tasks with history, parallel execution, and file storage."""
    
    def __init__(self, max_workers: int = 5):
        self.tasks: Dict[str, Task] = {}
        self.task_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        self.scheduler_thread = None
        self._task_counter = 0
        self._lock = threading.Lock()
        self._task_history: Dict[str, List[dict]] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active_futures: Dict[str, Future] = {}
        self._load_history()
        
    def _load_history(self):
        """Load task history from disk."""
        try:
            if os.path.exists(TASK_HISTORY_FILE):
                with open(TASK_HISTORY_FILE, 'r') as f:
                    self._task_history = json.load(f)
        except Exception as e:
            print(f"[TaskManager] Could not load history: {e}")
            self._task_history = {}
    
    def _save_history(self):
        """Save task history to disk."""
        try:
            with open(TASK_HISTORY_FILE, 'w') as f:
                json.dump(self._task_history, f, indent=2, default=str)
        except Exception as e:
            print(f"[TaskManager] Could not save history: {e}")
        
    def start(self):
        """Start the task manager."""
        if self.running:
            return
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.worker_thread.start()
        self.scheduler_thread.start()
        print("[TaskManager] Started")
        
    def stop(self):
        """Stop the task manager."""
        self.running = False
        
        # Cancel active futures
        for task_id, future in self._active_futures.items():
            if not future.done():
                future.cancel()
        
        # Shutdown executor
        self._executor.shutdown(wait=False)
        
        if self.worker_thread:
            self.worker_thread.join(timeout=2)
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=2)
        print("[TaskManager] Stopped")
        
    def add_task(self, name: str, func: Callable, args: tuple = (), 
                 kwargs: dict = None, interval: int = None,
                 use_history: bool = False, max_history: int = 10,
                 parallel: bool = True) -> str:
        """Add a new task. Returns task ID.
        
        Args:
            name: Task name (used for history lookup and folder name)
            func: Function to execute
            args: Positional arguments for function
            kwargs: Keyword arguments for function
            interval: If set, repeat every N seconds
            use_history: If True, pass previous results to function via 'previous_results' kwarg
            max_history: Maximum number of historical results to keep
            parallel: If True, task can run in parallel with others (default True)
        """
        with self._lock:
            self._task_counter += 1
            task_id = f"task_{self._task_counter}"
        
        # Load existing history for this task name
        existing_history = self._task_history.get(name, [])
        
        # Also load from file outputs if available
        file_outputs = load_task_outputs(name, limit=max_history)
        
        task = Task(
            id=task_id,
            name=name,
            func=func,
            args=args,
            kwargs=kwargs or {},
            interval=interval,
            use_history=use_history,
            max_history=max_history,
            parallel=parallel,
            history=[TaskResult(**h) if isinstance(h, dict) else h for h in existing_history[-max_history:]]
        )
        
        self.tasks[task_id] = task
        
        # Create task folder
        get_task_folder(name)
        
        if interval is None:
            # One-time task, queue immediately
            self.task_queue.put(task_id)
        
        return task_id
        
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.CANCELLED
            return True
        return False
        
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a task including history."""
        if task_id not in self.tasks:
            return {"error": "Task not found"}
            
        task = self.tasks[task_id]
        return {
            "id": task.id,
            "name": task.name,
            "status": task.status.value,
            "result": task.result,
            "error": task.error,
            "last_run": str(task.last_run) if task.last_run else None,
            "run_count": task.run_count,
            "is_recurring": task.interval is not None,
            "uses_history": task.use_history,
            "history_count": len(task.history),
            "parallel": task.parallel,
            "output_folder": get_task_folder(task.name)
        }
    
    def get_task_history(self, task_id: str = None, task_name: str = None) -> List[dict]:
        """Get execution history for a task by ID or name."""
        if task_id and task_id in self.tasks:
            task = self.tasks[task_id]
            return [{"timestamp": h.timestamp, "result": h.result, "error": h.error, "run": h.run_number} 
                    for h in task.history]
        elif task_name and task_name in self._task_history:
            return self._task_history[task_name]
        return []
    
    def get_task_outputs(self, task_id: str = None, task_name: str = None, limit: int = 10) -> List[dict]:
        """Get saved output files for a task."""
        name = task_name
        if task_id and task_id in self.tasks:
            name = self.tasks[task_id].name
        
        if name:
            return load_task_outputs(name, limit=limit)
        return []
    
    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """Get list of currently running tasks."""
        running = []
        for task_id, task in self.tasks.items():
            if task.status == TaskStatus.RUNNING:
                running.append({
                    "id": task_id,
                    "name": task.name,
                    "started": str(task.last_run) if task.last_run else None
                })
        return running
        
    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks."""
        return [self.get_task_status(tid) for tid in self.tasks]
        
    def _worker_loop(self):
        """Worker thread that dispatches tasks for parallel execution."""
        while self.running:
            try:
                task_id = self.task_queue.get(timeout=0.5)
                
                if task_id not in self.tasks:
                    continue
                    
                task = self.tasks[task_id]
                
                if task.status == TaskStatus.CANCELLED:
                    continue
                
                # Submit task for parallel execution
                if task.parallel:
                    future = self._executor.submit(self._execute_task, task_id)
                    self._active_futures[task_id] = future
                    task.future = future
                else:
                    # Execute synchronously if not parallel
                    self._execute_task(task_id)
                    
            except queue.Empty:
                # Clean up completed futures
                self._cleanup_futures()
                continue
            except Exception as e:
                print(f"[TaskManager] Worker error: {e}")
    
    def _cleanup_futures(self):
        """Remove completed futures from tracking."""
        completed = [tid for tid, f in self._active_futures.items() if f.done()]
        for tid in completed:
            del self._active_futures[tid]
    
    def _execute_task(self, task_id: str):
        """Execute a single task."""
        if task_id not in self.tasks:
            return
            
        task = self.tasks[task_id]
        
        if task.status == TaskStatus.CANCELLED:
            return
            
        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now()
        
        try:
            # Prepare kwargs with history if needed
            kwargs = task.kwargs.copy()
            if task.use_history:
                # Load from file outputs for more complete history
                file_outputs = load_task_outputs(task.name, limit=task.max_history)
                kwargs['previous_results'] = [
                    {"timestamp": o.get("timestamp"), "result": o.get("result"), "run": o.get("run_number")}
                    for o in reversed(file_outputs)  # Oldest first
                ]
            
            result = task.func(*task.args, **kwargs)
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.run_count += 1
            
            # Save output to file
            output_file = save_task_output(task.name, task.run_count, result)
            
            # Store in memory history
            task_result = TaskResult(
                timestamp=datetime.now().isoformat(),
                result=result,
                run_number=task.run_count
            )
            task.history.append(task_result)
            
            # Trim history if needed
            if len(task.history) > task.max_history:
                task.history = task.history[-task.max_history:]
            
            # Update persistent history
            self._update_persistent_history(task)
            
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.run_count += 1
            
            # Save failure to file
            save_task_output(task.name, task.run_count, None, str(e))
            
            # Store failure in history too
            task_result = TaskResult(
                timestamp=datetime.now().isoformat(),
                result=None,
                error=str(e),
                run_number=task.run_count
            )
            task.history.append(task_result)
            self._update_persistent_history(task)
    
    def _update_persistent_history(self, task: Task):
        """Update persistent history for a task."""
        history_entries = [
            {"timestamp": h.timestamp, "result": h.result, "error": h.error, "run_number": h.run_number}
            for h in task.history
        ]
        self._task_history[task.name] = history_entries[-task.max_history:]
        self._save_history()
                
    def _scheduler_loop(self):
        """Scheduler thread for recurring tasks."""
        while self.running:
            try:
                now = datetime.now()
                
                for task_id, task in list(self.tasks.items()):
                    if task.status == TaskStatus.CANCELLED:
                        continue
                        
                    if task.interval is None:
                        continue
                        
                    # Check if it's time to run
                    if task.last_run is None:
                        # Never run, schedule now
                        self.task_queue.put(task_id)
                    else:
                        elapsed = (now - task.last_run).total_seconds()
                        if elapsed >= task.interval and task.status != TaskStatus.RUNNING:
                            task.status = TaskStatus.PENDING
                            self.task_queue.put(task_id)
                            
                time.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"[TaskManager] Scheduler error: {e}")


# Singleton instance
_manager = None

def get_task_manager() -> TaskManager:
    """Get or create the task manager singleton."""
    global _manager
    if _manager is None:
        _manager = TaskManager()
    return _manager
