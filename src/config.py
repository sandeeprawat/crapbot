"""Configuration loader for the AI Agent."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(r"C:\src\ai\.env")

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

# Agent settings
AGENT_NAME = "CrapBot"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 120
