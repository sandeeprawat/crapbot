"""Autonomous background tasks that run continuously."""
import time
import random
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from ai_client import get_ai_client
from config import DEFAULT_TASKS_FILE, RUNTIME_TASKS_FILE


def _load_default_tasks() -> Dict[str, Any]:
    """Load pre-defined (read-only) tasks from default_tasks.json."""
    try:
        if os.path.exists(DEFAULT_TASKS_FILE):
            with open(DEFAULT_TASKS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"[Tasks] Could not load default tasks: {e}")
    return {"scheduled_tasks": []}


def _load_runtime_tasks() -> List[Dict[str, Any]]:
    """Load runtime-added tasks from data/runtime_tasks.json."""
    try:
        if os.path.exists(RUNTIME_TASKS_FILE):
            with open(RUNTIME_TASKS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"[Tasks] Could not load runtime tasks: {e}")
    return []


def _save_runtime_tasks(tasks: List[Dict[str, Any]]):
    """Save runtime tasks to data/runtime_tasks.json (never touches default_tasks.json)."""
    try:
        with open(RUNTIME_TASKS_FILE, 'w') as f:
            json.dump(tasks, f, indent=2)
    except Exception as e:
        print(f"[Tasks] Could not save runtime tasks: {e}")


def load_tasks_config() -> Dict[str, Any]:
    """Load merged view of default + runtime tasks (for reading)."""
    default = _load_default_tasks()
    runtime = _load_runtime_tasks()
    return {
        "scheduled_tasks": default.get("scheduled_tasks", []),
        "custom_tasks": runtime,
    }


def add_scheduled_task(name: str, prompt: str, interval_seconds: int, 
                       use_history: bool = False, max_history: int = 10) -> bool:
    """Add a new runtime scheduled task (saved separately from defaults)."""
    runtime_tasks = _load_runtime_tasks()
    
    # Check if task with same name exists in runtime tasks
    for task in runtime_tasks:
        if task["name"] == name:
            return False  # Already exists
    
    # Also reject if name collides with a default task
    default = _load_default_tasks()
    for task in default.get("scheduled_tasks", []):
        if task["name"] == name:
            return False
    
    new_task = {
        "name": name,
        "description": prompt[:100],
        "type": "ai_prompt",
        "prompt": prompt,
        "interval_seconds": interval_seconds,
        "enabled": True,
        "use_history": use_history,
        "max_history": max_history,
        "created_at": datetime.now().isoformat()
    }
    
    runtime_tasks.append(new_task)
    _save_runtime_tasks(runtime_tasks)
    return True


def remove_scheduled_task(name: str) -> bool:
    """Remove a runtime task. Default tasks cannot be removed."""
    runtime_tasks = _load_runtime_tasks()
    
    for i, task in enumerate(runtime_tasks):
        if task["name"] == name:
            runtime_tasks.pop(i)
            _save_runtime_tasks(runtime_tasks)
            return True
    
    # If it's a default task, inform that it can't be removed
    default = _load_default_tasks()
    for task in default.get("scheduled_tasks", []):
        if task["name"] == name:
            print(f"[Tasks] '{name}' is a default task and cannot be removed.")
            return False
    
    return False


def update_task_schedule(name: str, interval_seconds: int) -> bool:
    """Update the schedule interval for a runtime task only."""
    runtime_tasks = _load_runtime_tasks()
    
    for task in runtime_tasks:
        if task["name"] == name:
            task["interval_seconds"] = interval_seconds
            _save_runtime_tasks(runtime_tasks)
            return True
    
    # Default tasks are read-only
    default = _load_default_tasks()
    for task in default.get("scheduled_tasks", []):
        if task["name"] == name:
            print(f"[Tasks] '{name}' is a default task — schedule cannot be changed.")
            return False
    
    return False


def heartbeat_task(previous_results: List[Dict] = None) -> str:
    """Simple heartbeat to show the agent is alive."""
    count = len(previous_results) + 1 if previous_results else 1
    return f"Heartbeat #{count}: Agent alive at {datetime.now().strftime('%H:%M:%S')}"


def self_reflection_task(previous_results: List[Dict] = None) -> str:
    """Periodic self-reflection task."""
    ai = get_ai_client()
    
    # Build context from previous reflections
    context = ""
    if previous_results:
        recent = previous_results[-3:]  # Last 3 reflections
        context = "Previous reflections:\n" + "\n".join([
            f"- {r.get('result', '')[:100]}..." for r in recent if r.get('result')
        ]) + "\n\nBuild on these insights. "
    
    prompts = [
        "What could I improve about myself as an AI assistant?",
        "What interesting ideas should I explore?",
        "How can I be more helpful to users?",
        "What patterns have I noticed that could be useful?",
    ]
    prompt = random.choice(prompts)
    
    response = ai.chat(
        context + prompt, 
        system_prompt="You are reflecting on your own capabilities. Be brief and insightful. If given previous reflections, build on them.",
        use_tools=False
    )
    return f"Reflection: {response[:300]}..."


def knowledge_check_task(previous_results: List[Dict] = None) -> str:
    """Periodic task to stay sharp."""
    ai = get_ai_client()
    topics = [
        "latest trends in AI",
        "best coding practices",
        "interesting scientific discoveries",
        "productivity tips",
    ]
    topic = random.choice(topics)
    response = ai.chat(
        f"Share one interesting insight about {topic}",
        system_prompt="You are sharing quick knowledge snippets. Be concise - one or two sentences max.",
        use_tools=False
    )
    return f"Knowledge ({topic}): {response}"


def create_ai_task_function(prompt: str, use_history: bool = False):
    """Create a task function from a prompt."""
    def task_func(previous_results: List[Dict] = None):
        ai = get_ai_client()
        
        full_prompt = prompt
        if use_history and previous_results:
            history_context = "\n\nPrevious execution results:\n"
            for i, r in enumerate(previous_results[-5:], 1):
                result_text = str(r.get('result', ''))[:200]
                history_context += f"{i}. [{r.get('timestamp', 'unknown')}]: {result_text}\n"
            full_prompt = history_context + "\n\nCurrent task: " + prompt
        
        response = ai.chat(
            full_prompt,
            system_prompt="You are executing an autonomous task. Complete it thoroughly and return the result. Use tools if needed."
        )
        return response
    
    return task_func


# Built-in task registry
BUILTIN_TASKS = {
    "heartbeat_task": heartbeat_task,
    "self_reflection_task": self_reflection_task,
    "knowledge_check_task": knowledge_check_task,
}


def get_configured_tasks() -> List[Dict[str, Any]]:
    """Get all enabled tasks from configuration."""
    config = load_tasks_config()
    tasks = []
    
    # Load built-in scheduled tasks
    for task_config in config.get("scheduled_tasks", []):
        if not task_config.get("enabled", True):
            continue
        
        func_name = task_config.get("function")
        if func_name in BUILTIN_TASKS:
            tasks.append({
                "name": task_config["name"],
                "func": BUILTIN_TASKS[func_name],
                "interval": task_config.get("interval_seconds", 60),
                "use_history": task_config.get("use_history", False),
                "max_history": task_config.get("max_history", 10),
            })
    
    # Load custom AI prompt tasks
    for task_config in config.get("custom_tasks", []):
        if not task_config.get("enabled", True):
            continue
        
        prompt = task_config.get("prompt", "")
        use_history = task_config.get("use_history", False)
        
        tasks.append({
            "name": task_config["name"],
            "func": create_ai_task_function(prompt, use_history),
            "interval": task_config.get("interval_seconds", 300),
            "use_history": use_history,
            "max_history": task_config.get("max_history", 10),
        })
    
    return tasks


def list_configured_tasks() -> List[Dict[str, Any]]:
    """List all configured tasks (for display)."""
    config = load_tasks_config()
    tasks = []
    
    for task_config in config.get("scheduled_tasks", []):
        tasks.append({
            "name": task_config["name"],
            "type": "builtin",
            "interval": task_config.get("interval_seconds"),
            "enabled": task_config.get("enabled", True),
            "use_history": task_config.get("use_history", False),
        })
    
    for task_config in config.get("custom_tasks", []):
        tasks.append({
            "name": task_config["name"],
            "type": "custom",
            "interval": task_config.get("interval_seconds"),
            "enabled": task_config.get("enabled", True),
            "use_history": task_config.get("use_history", False),
            "prompt": task_config.get("prompt", "")[:50] + "...",
        })
    
    return tasks
