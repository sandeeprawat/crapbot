"""AI Client wrapper for Azure OpenAI with multi-model, Bing grounding, and tool calling support."""
import time
import json
import requests
from openai import AzureOpenAI
from config import (
    MODELS,
    DEFAULT_MODEL,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    AZURE_AI_WUS_PROJECT_ENDPOINT,
    AZURE_AI_WUS_API_KEY,
    AZURE_AI_WUS_BING_RESOURCE_NAME,
)
from tools import get_tool_definitions, execute_tool, list_available_tools


class AIClient:
    """Wrapper for Azure OpenAI API calls with multi-model and tool calling support."""
    
    def __init__(self, model_name: str = None):
        self.current_model = model_name or DEFAULT_MODEL
        self._clients = {}
        self.conversation_history = []
        self.tools_enabled = True
        self.max_tool_iterations = 100
        
    def _get_client(self, model_name: str) -> AzureOpenAI:
        """Get or create client for a specific model."""
        if model_name not in self._clients:
            config = MODELS.get(model_name)
            if not config:
                raise ValueError(f"Unknown model: {model_name}")
            
            self._clients[model_name] = AzureOpenAI(
                azure_endpoint=config["endpoint"],
                api_key=config["api_key"],
                api_version=config["api_version"]
            )
        return self._clients[model_name]
    
    def switch_model(self, model_name: str) -> str:
        """Switch to a different model."""
        if model_name not in MODELS:
            return f"Unknown model. Available: {', '.join(MODELS.keys())}"
        self.current_model = model_name
        return f"Switched to {model_name}"
    
    def list_models(self) -> list:
        """List available models."""
        return list(MODELS.keys())
    
    def toggle_tools(self, enabled: bool = None) -> str:
        """Toggle tool calling on/off."""
        if enabled is not None:
            self.tools_enabled = enabled
        else:
            self.tools_enabled = not self.tools_enabled
        return f"Tools {'enabled' if self.tools_enabled else 'disabled'}"
    
    def get_available_tools(self) -> list:
        """Get list of available tools."""
        return list_available_tools()
        
    def reset_conversation(self):
        """Reset conversation history."""
        self.conversation_history = []
    
    def _get_system_prompt(self, enable_tools: bool) -> str:
        """Get the system prompt for the agent."""
        if not enable_tools:
            return "You are CrapBot, an intelligent AI assistant. Be helpful, concise, and accurate."
        
        return """You are CrapBot, an autonomous AI agent with the ability to execute code and use tools to accomplish tasks.

CAPABILITIES:
- Execute Python, JavaScript, and PowerShell code autonomously
- Make REST API calls to any endpoint
- Read and write files
- Search the web and fetch web pages
- Run shell commands
- Install packages (pip, npm)
- Create multi-file projects

AUTONOMOUS BEHAVIOR:
When given a task that requires computation, data processing, API calls, or any programming:
1. ALWAYS write and execute code to solve it - don't just explain how
2. If code fails, debug and try again
3. Show the actual results from execution
4. For complex tasks, break them into steps and execute each

EXAMPLES OF WHEN TO WRITE CODE:
- "Calculate X" → Write Python code to calculate it
- "Fetch data from API" → Write code to call the API and show results
- "Process this file" → Write code to read and process the file
- "Create a script that..." → Write and execute the script
- "Analyze..." → Write code to perform the analysis

IMPORTANT:
- Prefer action over explanation
- Execute code to verify your solutions work
- Use tools proactively, not just when explicitly asked
- If you're unsure, try it and see what happens"""
        
    def chat(self, user_message: str, system_prompt: str = None, model: str = None,
             use_tools: bool = None, tool_allowlist: list = None) -> str:
        """Send a message and get a response, with optional tool calling."""
        model_name = model or self.current_model
        client = self._get_client(model_name)
        config = MODELS[model_name]
        
        # Determine if we should use tools
        enable_tools = use_tools if use_tools is not None else self.tools_enabled
        
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({"role": "system", "content": self._get_system_prompt(enable_tools)})
        
        # Add conversation history
        messages.extend(self.conversation_history)
        
        # Add user message
        messages.append({"role": "user", "content": user_message})
        
        # Get tool definitions if enabled
        tools = get_tool_definitions() if enable_tools else None
        if tools and tool_allowlist:
            allow = set(tool_allowlist)
            tools = [t for t in tools if t.get("function", {}).get("name") in allow]
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self._call_with_tools(client, config, model_name, messages, tools)
                
                # Update conversation history
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": response})
                
                # Keep history manageable
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
                
                return response
                
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    return f"Error: {str(e)}"
                time.sleep(1)
        
        return "Failed to get response after retries."
    
    def _call_with_tools(self, client, config, model_name, messages, tools) -> str:
        """Make API call with tool calling support."""
        iteration = 0
        current_messages = messages.copy()
        
        while iteration < self.max_tool_iterations:
            iteration += 1
            
            # Build request parameters
            params = {
                "model": config["deployment"],
                "messages": current_messages,
                "timeout": REQUEST_TIMEOUT
            }
            
            # Add tools if available
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"
            
            # Model-specific parameters
            if model_name in ["gpt-5", "grok"]:
                params["max_completion_tokens"] = 4096
            else:
                params["max_tokens"] = 4096
                params["temperature"] = 0.7
            
            response = client.chat.completions.create(**params)
            message = response.choices[0].message
            
            # Check if there are tool calls
            if message.tool_calls:
                # Add assistant message with tool calls
                current_messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in message.tool_calls
                    ]
                })
                
                # Execute each tool call
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    try:
                        func_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        func_args = {}
                    
                    # Execute the tool
                    tool_result = execute_tool(func_name, func_args)
                    
                    # Add tool result to messages
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    })
                
                # Continue loop to get final response
                continue
            
            # No tool calls, return the response
            return message.content or ""
        
        return "Maximum tool iterations reached. Please try a simpler request."

    def search(self, query: str) -> str:
        """Search the web and return AI-summarized results."""
        # Since Bing grounding requires Azure AI Foundry portal configuration,
        # we'll use a practical approach: fetch from public news APIs and summarize
        
        # Try multiple search sources
        search_results = []
        
        # 1. Try to get news from a public API
        try:
            news = self._fetch_news_api(query)
            if news:
                search_results.extend(news)
        except:
            pass
        
        # 2. If we have results, summarize them with AI
        if search_results:
            return self._summarize_search_results(query, search_results)
        
        # 3. Fallback to AI knowledge with clear indication
        return self._fallback_search(query)
    
    def _fetch_news_api(self, query: str) -> list:
        """Fetch news from public APIs."""
        results = []
        
        # Try DuckDuckGo instant answer API (no key required)
        try:
            ddg_url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
            response = requests.get(ddg_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("Abstract"):
                    results.append({
                        "title": data.get("Heading", "Result"),
                        "snippet": data.get("Abstract"),
                        "source": data.get("AbstractSource", "DuckDuckGo")
                    })
                for topic in data.get("RelatedTopics", [])[:5]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "title": topic.get("Text", "")[:100],
                            "snippet": topic.get("Text"),
                            "source": "DuckDuckGo"
                        })
        except:
            pass
        
        # Try Wikipedia API for factual queries
        try:
            wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
            response = requests.get(wiki_url, timeout=10, headers={"User-Agent": "CrapBot/1.0"})
            if response.status_code == 200:
                data = response.json()
                if data.get("extract"):
                    results.append({
                        "title": data.get("title", query),
                        "snippet": data.get("extract"),
                        "source": "Wikipedia"
                    })
        except:
            pass
        
        return results
    
    def _summarize_search_results(self, query: str, results: list) -> str:
        """Summarize search results using AI."""
        results_text = "\n\n".join([
            f"**{r['title']}** ({r['source']})\n{r['snippet']}"
            for r in results[:10]
        ])
        
        prompt = f"""Based on these search results for "{query}", provide a helpful summary:

{results_text}

Provide a concise, informative response based on these results."""
        
        return self.chat(
            prompt,
            system_prompt="You are summarizing search results. Be factual and cite the sources provided.",
            use_tools=False  # Don't use tools for summarization
        )
    
    def _fallback_search(self, query: str, error: str = None) -> str:
        """Fallback search using the model's knowledge."""
        return self.chat(
            f"Search request: {query}\n\nProvide the most current and accurate information you have about this topic. Clearly indicate your knowledge cutoff if relevant.",
            system_prompt="You are a search assistant. Provide helpful, factual information. If the query is about current events, acknowledge your knowledge limitations.",
            use_tools=False
        )


# Singleton instance
_client = None

def get_ai_client() -> AIClient:
    """Get or create the AI client singleton."""
    global _client
    if _client is None:
        _client = AIClient()
    return _client
