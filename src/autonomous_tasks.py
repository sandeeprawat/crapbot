"""Autonomous background tasks that run continuously."""
import time
import random
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from ai_client import get_ai_client


# Task configuration file path
TASKS_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "tasks_config.json")


def load_tasks_config() -> Dict[str, Any]:
    """Load tasks configuration from file."""
    try:
        if os.path.exists(TASKS_CONFIG_FILE):
            with open(TASKS_CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"[Tasks] Could not load config: {e}")
    return {"scheduled_tasks": [], "custom_tasks": []}


def save_tasks_config(config: Dict[str, Any]):
    """Save tasks configuration to file."""
    try:
        with open(TASKS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"[Tasks] Could not save config: {e}")


def add_scheduled_task(name: str, prompt: str, interval_seconds: int, 
                       use_history: bool = False, max_history: int = 10) -> bool:
    """Add a new custom scheduled task to the configuration."""
    config = load_tasks_config()
    
    # Check if task with same name exists
    for task in config.get("custom_tasks", []):
        if task["name"] == name:
            return False  # Already exists
    
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
    
    if "custom_tasks" not in config:
        config["custom_tasks"] = []
    
    config["custom_tasks"].append(new_task)
    save_tasks_config(config)
    return True


def remove_scheduled_task(name: str) -> bool:
    """Remove a scheduled task from configuration."""
    config = load_tasks_config()
    
    # Check in custom tasks
    custom_tasks = config.get("custom_tasks", [])
    for i, task in enumerate(custom_tasks):
        if task["name"] == name:
            custom_tasks.pop(i)
            save_tasks_config(config)
            return True
    
    # Check in scheduled tasks (disable instead of remove)
    for task in config.get("scheduled_tasks", []):
        if task["name"] == name:
            task["enabled"] = False
            save_tasks_config(config)
            return True
    
    return False


def update_task_schedule(name: str, interval_seconds: int) -> bool:
    """Update the schedule interval for a task."""
    config = load_tasks_config()
    
    for task_list in [config.get("scheduled_tasks", []), config.get("custom_tasks", [])]:
        for task in task_list:
            if task["name"] == name:
                task["interval_seconds"] = interval_seconds
                save_tasks_config(config)
                return True
    
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
