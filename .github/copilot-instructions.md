# CrapBot - GitHub Copilot Instructions

## Project Overview

CrapBot is an autonomous AI agent system written in Python that provides:
- Autonomous code execution (Python, JavaScript, PowerShell)
- Background task management with scheduling capabilities
- Deep research system with autonomous planning and critical review
- Split-screen interface for real-time agent and critic collaboration
- Multi-model support (GPT-4, GPT-5, Grok)
- Tool system with 20+ integrated tools (file operations, web search, API calls)
- Bing grounding for web search

## Technology Stack

- **Language**: Python 3.7+
- **Key Dependencies**:
  - `openai>=1.0.0` - Azure OpenAI integration
  - `azure-identity` - Azure authentication
  - `python-dotenv` - Environment variable management
  - `aiohttp`, `asyncio` - Async operations
  - `requests` - HTTP requests
  - `windows-curses` - Windows terminal UI support

## Architecture

### Core Components

- `src/agent.py` - Main agent entry point and command-line interface
- `src/ai_client.py` - AI model interface with multi-model support
- `src/autonomous_agent.py` - Autonomous agent and critic system
- `src/deep_research_agent.py` - Deep research system with planning and review
- `src/tools.py` - Tool definitions and implementations
- `src/task_manager.py` - Background task management
- `src/autonomous_tasks.py` - Autonomous task execution
- `src/terminal.py` - Interactive terminal interface
- `src/split_terminal.py` - Split-screen curses-based UI
- `src/config.py` - Configuration management
- `src/web_app.py` - Flask web UI (if present)

### Data Storage Structure

```
data/
├── agent_state/           # Agent state and instructions
├── research_state/        # Research sessions and results
├── task_data/            # Task outputs and history
└── workspace/            # Code execution workspace
```

## Development Guidelines

### Setup and Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your Azure OpenAI API keys and endpoints
```

### Running the Project

```bash
# Start with split-screen interface (default)
python src/agent.py

# Start with classic terminal interface
python src/agent.py --classic

# Run tests
python test_research_basic.py

# Run web UI (if available)
python src/web_app.py
```

### Testing

- Basic tests are in `test_research_basic.py`
- Run with: `python test_research_basic.py`
- Full integration tests require API keys configured in `.env`
- No pytest framework is used; tests are plain Python scripts

### Code Style and Conventions

1. **Python Version**: Target Python 3.7+ for compatibility
2. **Async/Await**: Use async/await patterns for I/O operations
3. **Error Handling**: Always handle API errors and provide meaningful error messages
4. **Environment Variables**: Use `python-dotenv` for configuration, never hardcode secrets
5. **Logging**: Use the logging module for debugging and monitoring
6. **Type Hints**: Use type hints where appropriate for clarity

### Key Features to Preserve

1. **Tool System**: When adding new tools, follow the pattern in `src/tools.py`
2. **Multi-Model Support**: Maintain compatibility with multiple AI models
3. **Background Tasks**: Use the task manager for long-running operations
4. **State Persistence**: Save important state in the `data/` directory
5. **Research System**: Autonomous planning, execution, and critical review cycle

### API and Configuration

- Azure OpenAI endpoints are configured via environment variables
- Multiple model configurations supported (GPT-5, GPT-4o, GPT-3.5, Grok)
- Bing grounding requires Azure AI Project endpoints
- All sensitive credentials must be in `.env` and never committed to git

### File Operations

- Agent workspace is in `data/workspace/`
- Research results are stored in `data/research_state/`
- Task outputs are stored in `data/task_data/`
- Never modify files outside the project directory without explicit permission

### Security Considerations

1. **API Keys**: Never expose API keys in code or logs
2. **Code Execution**: The agent executes arbitrary code - be cautious with user input
3. **File Access**: Limit file operations to designated directories
4. **Web Search**: Validate and sanitize search queries and results

## Common Tasks

### Adding a New Tool

1. Define the tool in `src/tools.py` following the existing pattern
2. Add the tool to the tools list
3. Update documentation if it's a user-facing feature

### Adding a New Command

1. Add the command handler in `src/agent.py` or appropriate module
2. Update the help text
3. Test thoroughly with different inputs

### Modifying Research System

1. Changes to research logic go in `src/deep_research_agent.py`
2. Maintain the orchestrator pattern: problem analysis → execution → review
3. Preserve the quality scoring system (1-10 scale)

### Working with Background Tasks

1. Use `src/task_manager.py` for scheduling
2. Tasks should be serializable to JSON
3. Store task state in `data/task_data/`

## Documentation

- Main docs: `README.md`
- Deep Research: `DEEP_RESEARCH_README.md`
- Examples: `examples_research.py`
- Implementation notes: `IMPLEMENTATION_SUMMARY.md`

## When Making Changes

1. **Preserve existing functionality** - this is a working system
2. **Test with actual API calls** when possible (requires `.env` setup)
3. **Follow the async patterns** used throughout the codebase
4. **Update documentation** if adding new features
5. **Maintain backward compatibility** with existing commands and APIs
6. **Consider the autonomous nature** - changes should work without human intervention

## Things to Avoid

- Don't break the split-screen UI by blocking I/O operations
- Don't mix sync and async code without proper handling
- Don't add dependencies that conflict with Python 3.7 compatibility
- Don't modify the core agent loop without understanding the full flow
- Don't remove or disable existing tools without good reason
- Don't hardcode file paths - use relative paths from project root
