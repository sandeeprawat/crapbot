"""Tool definitions and implementations for the AI Agent."""
import json
import requests
import subprocess
import os
import tempfile
import shutil
from typing import Any, Dict, List, Callable
from datetime import datetime
from config import DATA_DIR, AGENT_WORKSPACE


# Tool registry
TOOLS: Dict[str, Dict[str, Any]] = {}

# Code execution workspace — inside the agent's data folder
CODE_WORKSPACE = AGENT_WORKSPACE
os.makedirs(CODE_WORKSPACE, exist_ok=True)


def _is_inside_data_dir(path: str) -> bool:
    """Check whether a resolved path is inside the agent's data folder."""
    try:
        resolved = os.path.realpath(os.path.abspath(path))
        return resolved.startswith(os.path.realpath(DATA_DIR))
    except Exception:
        return False


def _resolve_safe_path(path: str) -> str:
    """Resolve a user-supplied path so it stays inside DATA_DIR.
    
    Relative paths are resolved relative to DATA_DIR.
    Absolute paths are accepted only if they fall inside DATA_DIR.
    """
    if os.path.isabs(path):
        resolved = os.path.realpath(path)
    else:
        resolved = os.path.realpath(os.path.join(DATA_DIR, path))
    
    if not resolved.startswith(os.path.realpath(DATA_DIR)):
        raise PermissionError(
            f"Access denied: path '{path}' is outside the agent's data folder ({DATA_DIR})"
        )
    return resolved


def register_tool(name: str, description: str, parameters: dict, func: Callable):
    """Register a tool for the agent to use."""
    TOOLS[name] = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "function": func,
    }


def get_tool_definitions() -> List[dict]:
    """Get OpenAI-compatible tool definitions."""
    definitions = []
    for name, tool in TOOLS.items():
        definitions.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
        })
    return definitions


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with given arguments."""
    if name not in TOOLS:
        return json.dumps({"error": f"Unknown tool: {name}"})
    
    try:
        result = TOOLS[name]["function"](**arguments)
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2, default=str)
        return str(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============== Tool Implementations ==============

def rest_api_call(method: str, url: str, headers: dict = None, body: dict = None, 
                  params: dict = None, timeout: int = 30) -> dict:
    """Make a REST API call."""
    try:
        headers = headers or {}
        
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=body if body else None,
            params=params,
            timeout=timeout
        )
        
        # Try to parse JSON response
        try:
            response_body = response.json()
        except:
            response_body = response.text[:2000] if len(response.text) > 2000 else response.text
        
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response_body,
            "success": 200 <= response.status_code < 300
        }
    except requests.exceptions.Timeout:
        return {"error": "Request timed out", "success": False}
    except requests.exceptions.ConnectionError:
        return {"error": "Connection failed", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


def get_current_time(timezone: str = "UTC") -> dict:
    """Get current date and time."""
    now = datetime.now()
    return {
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "timezone": timezone
    }


def read_file(path: str, max_lines: int = 100) -> dict:
    """Read contents of a file (must be inside data folder)."""
    try:
        path = _resolve_safe_path(path)
        if not os.path.exists(path):
            return {"error": f"File not found: {path}"}
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        if len(lines) > max_lines:
            content = ''.join(lines[:max_lines])
            return {
                "content": content,
                "truncated": True,
                "total_lines": len(lines),
                "shown_lines": max_lines
            }
        
        return {
            "content": ''.join(lines),
            "truncated": False,
            "total_lines": len(lines)
        }
    except Exception as e:
        return {"error": str(e)}


def write_file(path: str, content: str, mode: str = "write") -> dict:
    """Write content to a file (must be inside data folder)."""
    try:
        path = _resolve_safe_path(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file_mode = 'a' if mode == "append" else 'w'
        with open(path, file_mode, encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "path": path, "mode": mode}
    except Exception as e:
        return {"error": str(e), "success": False}


def run_command(command: str, timeout: int = 60) -> dict:
    """Run a shell command (working directory is agent's data folder)."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=DATA_DIR
        )
        return {
            "stdout": result.stdout[:5000] if len(result.stdout) > 5000 else result.stdout,
            "stderr": result.stderr[:2000] if len(result.stderr) > 2000 else result.stderr,
            "exit_code": result.returncode,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


def list_directory(path: str = ".") -> dict:
    """List contents of a directory (must be inside data folder)."""
    try:
        path = _resolve_safe_path(path)
        if not os.path.exists(path):
            return {"error": f"Directory not found: {path}"}
        
        items = []
        for item in os.listdir(path):
            full_path = os.path.join(path, item)
            items.append({
                "name": item,
                "type": "directory" if os.path.isdir(full_path) else "file",
                "size": os.path.getsize(full_path) if os.path.isfile(full_path) else None
            })
        
        return {"path": path, "items": items, "count": len(items)}
    except Exception as e:
        return {"error": str(e)}


def http_get(url: str, headers: dict = None) -> dict:
    """Simple HTTP GET request."""
    return rest_api_call("GET", url, headers=headers)


def http_post(url: str, body: dict, headers: dict = None) -> dict:
    """Simple HTTP POST request."""
    return rest_api_call("POST", url, headers=headers, body=body)


def calculate(expression: str) -> dict:
    """Evaluate a mathematical expression."""
    try:
        # Safe evaluation of math expressions
        allowed_names = {
            'abs': abs, 'round': round, 'min': min, 'max': max,
            'sum': sum, 'pow': pow, 'len': len,
        }
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e), "expression": expression}


def json_parse(json_string: str) -> dict:
    """Parse a JSON string."""
    try:
        parsed = json.loads(json_string)
        return {"success": True, "data": parsed}
    except json.JSONDecodeError as e:
        return {"error": str(e), "success": False}


def environment_info() -> dict:
    """Get environment information."""
    return {
        "platform": os.name,
        "cwd": os.getcwd(),
        "user": os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
        "python_version": subprocess.run(
            ["python", "--version"], 
            capture_output=True, text=True
        ).stdout.strip(),
        "data_directory": DATA_DIR,
        "code_workspace": CODE_WORKSPACE
    }


# ============== Code Execution Tools ==============

def execute_python(code: str, filename: str = None) -> dict:
    """Execute Python code."""
    filename = filename or f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    filepath = os.path.join(CODE_WORKSPACE, filename)
    
    try:
        # Write code to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Execute
        result = subprocess.run(
            ["python", filepath],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=CODE_WORKSPACE
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:10000] if result.stdout else "",
            "stderr": result.stderr[:5000] if result.stderr else "",
            "exit_code": result.returncode,
            "file": filepath
        }
    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out (120s limit)", "success": False, "file": filepath}
    except Exception as e:
        return {"error": str(e), "success": False}


def execute_javascript(code: str, filename: str = None) -> dict:
    """Execute JavaScript/Node.js code."""
    filename = filename or f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.js"
    filepath = os.path.join(CODE_WORKSPACE, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        
        result = subprocess.run(
            ["node", filepath],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=CODE_WORKSPACE
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:10000] if result.stdout else "",
            "stderr": result.stderr[:5000] if result.stderr else "",
            "exit_code": result.returncode,
            "file": filepath
        }
    except FileNotFoundError:
        return {"error": "Node.js not found. Install Node.js to run JavaScript.", "success": False}
    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out (120s limit)", "success": False, "file": filepath}
    except Exception as e:
        return {"error": str(e), "success": False}


def execute_powershell(code: str, filename: str = None) -> dict:
    """Execute PowerShell code."""
    filename = filename or f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ps1"
    filepath = os.path.join(CODE_WORKSPACE, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", filepath],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=CODE_WORKSPACE
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:10000] if result.stdout else "",
            "stderr": result.stderr[:5000] if result.stderr else "",
            "exit_code": result.returncode,
            "file": filepath
        }
    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out (120s limit)", "success": False, "file": filepath}
    except Exception as e:
        return {"error": str(e), "success": False}


def execute_code(language: str, code: str, filename: str = None) -> dict:
    """Execute code in the specified language."""
    language = language.lower().strip()
    
    executors = {
        "python": execute_python,
        "py": execute_python,
        "javascript": execute_javascript,
        "js": execute_javascript,
        "node": execute_javascript,
        "powershell": execute_powershell,
        "ps1": execute_powershell,
    }
    
    if language not in executors:
        return {
            "error": f"Unsupported language: {language}. Supported: python, javascript, powershell",
            "success": False
        }
    
    return executors[language](code, filename)


def create_and_run_project(project_type: str, name: str, code_files: dict) -> dict:
    """Create a project with multiple files and run it."""
    project_dir = os.path.join(CODE_WORKSPACE, name)
    
    try:
        # Create project directory
        os.makedirs(project_dir, exist_ok=True)
        
        # Write all files
        created_files = []
        for filename, content in code_files.items():
            filepath = os.path.join(project_dir, filename)
            # Create subdirectories if needed
            os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            created_files.append(filepath)
        
        # Determine entry point and run
        if project_type == "python":
            entry = "main.py" if "main.py" in code_files else list(code_files.keys())[0]
            result = subprocess.run(
                ["python", entry],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=project_dir
            )
        elif project_type in ["javascript", "node"]:
            # Install dependencies if package.json exists
            if "package.json" in code_files:
                subprocess.run(["npm", "install"], cwd=project_dir, capture_output=True, timeout=120)
            entry = "index.js" if "index.js" in code_files else list(code_files.keys())[0]
            result = subprocess.run(
                ["node", entry],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=project_dir
            )
        else:
            return {"error": f"Unknown project type: {project_type}", "success": False}
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:10000] if result.stdout else "",
            "stderr": result.stderr[:5000] if result.stderr else "",
            "exit_code": result.returncode,
            "project_dir": project_dir,
            "files_created": created_files
        }
        
    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out", "success": False, "project_dir": project_dir}
    except Exception as e:
        return {"error": str(e), "success": False}


def install_package(package_manager: str, packages: list) -> dict:
    """Install packages using pip, npm, etc."""
    try:
        if package_manager == "pip":
            cmd = ["pip", "install"] + packages
        elif package_manager == "npm":
            cmd = ["npm", "install"] + packages
        else:
            return {"error": f"Unknown package manager: {package_manager}", "success": False}
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=CODE_WORKSPACE
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:5000] if result.stdout else "",
            "stderr": result.stderr[:2000] if result.stderr else "",
            "packages": packages
        }
    except subprocess.TimeoutExpired:
        return {"error": "Installation timed out", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


def list_code_workspace() -> dict:
    """List files in the code workspace."""
    try:
        items = []
        for root, dirs, files in os.walk(CODE_WORKSPACE):
            rel_root = os.path.relpath(root, CODE_WORKSPACE)
            for f in files:
                rel_path = os.path.join(rel_root, f) if rel_root != "." else f
                items.append(rel_path)
        return {"workspace": CODE_WORKSPACE, "files": items[:100], "count": len(items)}
    except Exception as e:
        return {"error": str(e)}


def read_code_file(filename: str) -> dict:
    """Read a file from the code workspace."""
    filepath = os.path.join(CODE_WORKSPACE, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"file": filename, "content": content[:20000], "truncated": len(content) > 20000}
    except FileNotFoundError:
        return {"error": f"File not found: {filename}"}
    except Exception as e:
        return {"error": str(e)}


def cleanup_workspace(older_than_hours: int = 24) -> dict:
    """Clean up old files from code workspace."""
    try:
        deleted = 0
        cutoff = datetime.now().timestamp() - (older_than_hours * 3600)
        
        for item in os.listdir(CODE_WORKSPACE):
            path = os.path.join(CODE_WORKSPACE, item)
            if os.path.getmtime(path) < cutoff:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                deleted += 1
        
        return {"deleted": deleted, "workspace": CODE_WORKSPACE}
    except Exception as e:
        return {"error": str(e)}


def web_search(query: str, num_results: int = 5) -> dict:
    """Search the web using public APIs."""
    results = []
    
    # DuckDuckGo instant answers (no API key needed)
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
        response = requests.get(ddg_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", "Result"),
                    "snippet": data.get("Abstract"),
                    "url": data.get("AbstractURL", ""),
                    "source": data.get("AbstractSource", "DuckDuckGo")
                })
            for topic in data.get("RelatedTopics", [])[:num_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                        "snippet": topic.get("Text"),
                        "url": topic.get("FirstURL", ""),
                        "source": "DuckDuckGo"
                    })
    except Exception as e:
        pass
    
    # Wikipedia for knowledge queries
    try:
        wiki_search_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={query}&limit={num_results}&format=json"
        response = requests.get(wiki_search_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if len(data) >= 4:
                titles, _, snippets, urls = data[0], data[1], data[2], data[3]
                for i, title in enumerate(titles[:num_results]):
                    if isinstance(title, str) and i < len(urls):
                        results.append({
                            "title": title,
                            "snippet": snippets[i] if i < len(snippets) else "",
                            "url": urls[i] if i < len(urls) else "",
                            "source": "Wikipedia"
                        })
    except:
        pass
    
    if results:
        return {"success": True, "query": query, "results": results[:num_results], "count": len(results)}
    else:
        return {"success": False, "query": query, "results": [], "message": "No results found"}


def fetch_webpage(url: str, max_length: int = 5000) -> dict:
    """Fetch and extract text content from a webpage."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Basic HTML to text extraction
        import re
        text = response.text
        
        # Remove scripts and styles
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Decode HTML entities
        import html
        text = html.unescape(text)
        
        truncated = len(text) > max_length
        text = text[:max_length]
        
        return {
            "success": True,
            "url": url,
            "content": text,
            "truncated": truncated,
            "length": len(text)
        }
    except Exception as e:
        return {"success": False, "url": url, "error": str(e)}


# ============== Register All Tools ==============

register_tool(
    name="rest_api",
    description="Make a REST API call to any URL. Supports GET, POST, PUT, DELETE, PATCH methods.",
    parameters={
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                "description": "HTTP method"
            },
            "url": {
                "type": "string",
                "description": "The URL to call"
            },
            "headers": {
                "type": "object",
                "description": "Optional HTTP headers as key-value pairs"
            },
            "body": {
                "type": "object",
                "description": "Optional request body for POST/PUT/PATCH"
            },
            "params": {
                "type": "object",
                "description": "Optional query parameters"
            },
            "timeout": {
                "type": "integer",
                "description": "Request timeout in seconds (default 30)"
            }
        },
        "required": ["method", "url"]
    },
    func=rest_api_call
)

register_tool(
    name="http_get",
    description="Make a simple HTTP GET request to fetch data from a URL.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch"
            },
            "headers": {
                "type": "object",
                "description": "Optional HTTP headers"
            }
        },
        "required": ["url"]
    },
    func=http_get
)

register_tool(
    name="http_post",
    description="Make an HTTP POST request to send data to a URL.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to post to"
            },
            "body": {
                "type": "object",
                "description": "The JSON body to send"
            },
            "headers": {
                "type": "object",
                "description": "Optional HTTP headers"
            }
        },
        "required": ["url", "body"]
    },
    func=http_post
)

register_tool(
    name="get_time",
    description="Get the current date and time.",
    parameters={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "Timezone (default UTC)"
            }
        },
        "required": []
    },
    func=get_current_time
)

register_tool(
    name="read_file",
    description="Read the contents of a file from the filesystem.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read"
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum lines to read (default 100)"
            }
        },
        "required": ["path"]
    },
    func=read_file
)

register_tool(
    name="write_file",
    description="Write content to a file. Can create new files or overwrite/append to existing ones.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write"
            },
            "content": {
                "type": "string",
                "description": "Content to write"
            },
            "mode": {
                "type": "string",
                "enum": ["write", "append"],
                "description": "Write mode: 'write' to overwrite, 'append' to add to end"
            }
        },
        "required": ["path", "content"]
    },
    func=write_file
)

register_tool(
    name="run_command",
    description="Execute a shell command and return the output.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 60)"
            }
        },
        "required": ["command"]
    },
    func=run_command
)

register_tool(
    name="list_directory",
    description="List files and folders in a directory.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path (default: current directory)"
            }
        },
        "required": []
    },
    func=list_directory
)

register_tool(
    name="calculate",
    description="Evaluate a mathematical expression.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Math expression to evaluate (e.g., '2 + 2 * 3')"
            }
        },
        "required": ["expression"]
    },
    func=calculate
)

register_tool(
    name="environment_info",
    description="Get information about the current environment (OS, user, working directory, code workspace).",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    },
    func=environment_info
)

# ============== Code Execution Tool Registrations ==============

register_tool(
    name="execute_code",
    description="Write and execute code in Python, JavaScript, or PowerShell. Use this to run scripts, perform calculations, process data, or accomplish any programming task.",
    parameters={
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "enum": ["python", "javascript", "powershell"],
                "description": "Programming language to use"
            },
            "code": {
                "type": "string",
                "description": "The code to execute"
            },
            "filename": {
                "type": "string",
                "description": "Optional filename for the script"
            }
        },
        "required": ["language", "code"]
    },
    func=execute_code
)

register_tool(
    name="execute_python",
    description="Execute Python code. Great for data processing, calculations, web scraping, file manipulation, and general programming.",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute"
            },
            "filename": {
                "type": "string",
                "description": "Optional filename (default: auto-generated)"
            }
        },
        "required": ["code"]
    },
    func=execute_python
)

register_tool(
    name="execute_javascript",
    description="Execute JavaScript/Node.js code. Good for async operations, JSON processing, and Node.js scripts.",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "JavaScript code to execute with Node.js"
            },
            "filename": {
                "type": "string",
                "description": "Optional filename (default: auto-generated)"
            }
        },
        "required": ["code"]
    },
    func=execute_javascript
)

register_tool(
    name="execute_powershell",
    description="Execute PowerShell code. Useful for Windows system administration, file operations, and automation.",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "PowerShell code to execute"
            },
            "filename": {
                "type": "string",
                "description": "Optional filename (default: auto-generated)"
            }
        },
        "required": ["code"]
    },
    func=execute_powershell
)

register_tool(
    name="create_project",
    description="Create a multi-file project and run it. Use for complex applications with multiple files.",
    parameters={
        "type": "object",
        "properties": {
            "project_type": {
                "type": "string",
                "enum": ["python", "javascript"],
                "description": "Type of project"
            },
            "name": {
                "type": "string",
                "description": "Project name (will be the folder name)"
            },
            "code_files": {
                "type": "object",
                "description": "Dictionary of filename -> code content pairs"
            }
        },
        "required": ["project_type", "name", "code_files"]
    },
    func=create_and_run_project
)

register_tool(
    name="install_package",
    description="Install packages using pip (Python) or npm (Node.js).",
    parameters={
        "type": "object",
        "properties": {
            "package_manager": {
                "type": "string",
                "enum": ["pip", "npm"],
                "description": "Package manager to use"
            },
            "packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of package names to install"
            }
        },
        "required": ["package_manager", "packages"]
    },
    func=install_package
)

register_tool(
    name="list_code_workspace",
    description="List all files in the code execution workspace.",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    },
    func=list_code_workspace
)

register_tool(
    name="read_code_file",
    description="Read a file from the code workspace.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Filename or path relative to code workspace"
            }
        },
        "required": ["filename"]
    },
    func=read_code_file
)

register_tool(
    name="cleanup_workspace",
    description="Clean up old files from the code workspace.",
    parameters={
        "type": "object",
        "properties": {
            "older_than_hours": {
                "type": "integer",
                "description": "Delete files older than this many hours (default: 24)"
            }
        },
        "required": []
    },
    func=cleanup_workspace
)

register_tool(
    name="web_search",
    description="Search the web for information using DuckDuckGo and Wikipedia. Returns relevant results with snippets and URLs.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5)"
            }
        },
        "required": ["query"]
    },
    func=web_search
)

register_tool(
    name="fetch_webpage",
    description="Fetch and extract text content from a webpage URL. Useful for reading articles, documentation, or any web page.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the webpage to fetch"
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum characters to return (default: 5000)"
            }
        },
        "required": ["url"]
    },
    func=fetch_webpage
)


def list_available_tools() -> List[str]:
    """List all available tool names."""
    return list(TOOLS.keys())
