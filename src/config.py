"""Configuration loader for the AI Agent."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
# Try project root first, fall back to original location
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_env_path = os.path.join(_PROJECT_ROOT, ".env")
if not os.path.exists(_env_path):
    _env_path = r"C:\src\ai\.env"
load_dotenv(_env_path)

# Available Models Configuration
MODELS = {
    "gpt-5": {
        "endpoint": os.getenv("AZURE_OAI_GPT5_ENDPOINT"),
        "api_key": os.getenv("AZURE_OAI_GPT5_API_KEY"),
        "deployment": "gpt-5",
        "api_version": "2024-12-01-preview",
    },
    "gpt-4o": {
        "endpoint": os.getenv("AZURE_OAI_EUS2_ENDPOINT"),
        "api_key": os.getenv("AZURE_OAI_EUS2_API_KEY"),
        "deployment": os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        "api_version": "2024-12-01-preview",
    },
    "gpt-35": {
        "endpoint": os.getenv("AZURE_OAI_GPT35_ENDPOINT"),
        "api_key": os.getenv("AZURE_OAI_GPT35_API_KEY"),
        "deployment": "gpt-35-turbo",
        "api_version": "2024-06-01",
    },
    "grok": {
        "endpoint": os.getenv("AZURE_OAI_GPT5_ENDPOINT"),  # Uses same endpoint
        "api_key": os.getenv("GROK_API_KEY"),
        "deployment": "grok-4",
        "api_version": "2024-05-01-preview",
    },
}

# Default model
DEFAULT_MODEL = "gpt-5"

# Bing Grounding Configuration
BING_RESOURCE_NAME = os.getenv("BING_RESOURCE_NAME", "aibcazaicampbing")
BING_GROUNDING_MODEL = os.getenv("MODEL_BING_GROUNDING_BASE", "gpt-5")

# Project endpoints for Bing grounding
SEARCH_PROJECT_ENDPOINT = os.getenv("SEARCH_PROJECT_ENDPOINT")
GPT_PROJECT_ENDPOINT = os.getenv("GPT_PROJECT_ENDPOINT")
AZURE_AI_WUS_PROJECT_ENDPOINT = os.getenv("AZURE_AI_WUS_PROJECT_ENDPOINT")
AZURE_AI_WUS_API_KEY = os.getenv("AZURE_AI_WUS_API_KEY")
AZURE_AI_WUS_BING_RESOURCE_NAME = os.getenv("AZURE_AI_WUS_BING_RESOURCE_NAME")

# Paths — everything the agent touches lives under DATA_DIR
DATA_DIR = os.path.abspath(os.path.join(_PROJECT_ROOT, "data"))
TASK_DATA_DIR = os.path.join(DATA_DIR, "task_data")
RUNTIME_TASKS_FILE = os.path.join(DATA_DIR, "runtime_tasks.json")
AGENT_WORKSPACE = os.path.join(DATA_DIR, "workspace")
OUTPUTS_DIR = os.path.join(DATA_DIR, "outputs")
DEFAULT_TASKS_FILE = os.path.abspath(os.path.join(_PROJECT_ROOT, "default_tasks.json"))

# Ensure data directories exist
for _d in [DATA_DIR, TASK_DATA_DIR, AGENT_WORKSPACE, OUTPUTS_DIR]:
    os.makedirs(_d, exist_ok=True)

# Agent settings
AGENT_NAME = "CrapBot"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 120
