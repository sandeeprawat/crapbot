# CrapBot - Autonomous AI Agent

![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)

An intelligent autonomous AI agent with background task management, autonomous code execution, and now featuring a **Deep Research System** with autonomous planning and critical review.

## Features

### Core Capabilities
- **Autonomous Execution**: Agent can write and execute code (Python, JavaScript, PowerShell) to complete tasks
- **Background Tasks**: Scheduled and one-time tasks that run continuously
- **Tool System**: Integrated tools for file operations, web search, API calls, and more
- **Multi-Model Support**: Switch between different AI models (GPT-4, GPT-5, etc.)
- **Split-Screen Interface**: Real-time view of agent and critic working together

### 🆕 Deep Research System

A sophisticated research system featuring:
- **Autonomous Planning**: Adapts research strategy to problem type
- **Multi-Method Research**: Web search (Bing grounding), code analysis, data gathering
- **Critical Review**: Separate reviewer agent evaluates quality (1-10 scoring)
- **Iterative Improvement**: Automatic refinement based on feedback
- **Researcher-Reviewer Discussion**: Agents collaborate to reach consensus

Perfect for:
- 📈 Financial analysis and investment research
- 🤔 Philosophical inquiry and concept generation
- 🔬 Technical problem solving
- 📊 Market trend analysis
- 💡 Creative ideation with quality validation

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/sandeeprawat/crapbot.git
cd crapbot

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Edit `.env` file with your Azure OpenAI credentials:
```
AZURE_OAI_GPT5_ENDPOINT=your_endpoint
AZURE_OAI_GPT5_API_KEY=your_api_key
# ... other model configurations
```

### Running CrapBot

```bash
# Start with split-screen interface (default)
python src/agent.py

# Start with classic terminal interface
python src/agent.py --classic
```

## Usage

### Basic Commands

```bash
help              # Show all commands
chat <message>    # Chat with the AI
do <task>         # Execute task autonomously
search <query>    # Web search

# Deep Research (NEW!)
research <problem>  # Run autonomous research with review
```

### Deep Research Examples

```bash
# Investment research
research Identify 3-5 stocks with growth potential in AI sector

# Philosophical inquiry
research Come up with a novel philosophical concept about AI consciousness

# Technical analysis
research Design an efficient algorithm for real-time anomaly detection

# Market analysis
research Analyze renewable energy trends for next 3 years
```

### Task Management

```bash
task <description>           # Create one-time background task
schedule <name> <sec> <task> # Schedule recurring task
tasks                        # List all tasks
status <id>                  # Check task status
cancel <id>                  # Cancel a task
```

### Agent Control (Split-Screen Mode)

```bash
stop [agent|critic|both]   # Stop agents
start [agent|critic|both]  # Start agents
pause [agent|critic|both]  # Pause agents
resume [agent|critic|both] # Resume agents
instruct <target> <text>   # Change agent instructions (single-line)
topic                      # Set discussion topic (multi-line editor)
fresh                      # Clear session & restart both agents
agents                     # Show status of both agents
```

#### Setting a Topic for Agent/Critic Discussion

The `topic` command allows you to provide multi-line text input to guide the Agent/Critic session:

```bash
# In split-screen mode
topic
```

This will:
1. Open your preferred text editor (set via `EDITOR` environment variable, defaults to `nano`)
2. Allow you to enter multi-line text describing a topic or theme for discussion
3. Lines starting with `#` are treated as comments and ignored
4. When you save and close the editor, the topic is added to both Agent and Critic instructions

**Example use cases:**
- Provide a detailed research topic for the agents to explore
- Set constraints or guidelines for the discussion
- Give background context for a complex problem

## Deep Research System

### How It Works

1. **Problem Analysis**: Agent analyzes the problem type and creates a tailored research plan
2. **Research Execution**: Executes plan using web search, code analysis, and reasoning
3. **Quality Iteration**: Refines research if initial findings are insufficient
4. **Critical Review**: Reviewer agent evaluates quality and provides feedback
5. **Discussion & Refinement**: If quality is below threshold, agents discuss improvements
6. **Final Answer**: Delivers comprehensive, validated answer with quality score

### Python API

```python
from deep_research_agent import run_deep_research

# Simple usage
result = run_deep_research("Your research question")

# With configuration
from deep_research_agent import ResearchOrchestrator

orchestrator = ResearchOrchestrator(on_output=print)
result = orchestrator.conduct_research(
    problem="Your question",
    context="Additional context",
    min_score=8,      # Quality threshold (1-10)
    max_attempts=3    # Max research attempts
)

print(f"Score: {result['final_score']}/10")
print(f"Answer: {result['attempts'][-1]['research']['final_answer']}")
```

### Example Scripts

Run the included examples:

```bash
python examples_research.py
```

Choose from:
1. Stock/Investment Research
2. Novel Philosophical Concepts
3. Technical Problem Solving
4. Market Trend Analysis

## Architecture

### Components

- `src/agent.py` - Main agent entry point
- `src/ai_client.py` - AI model interface with multi-model support
- `src/tools.py` - Tool definitions and implementations
- `src/task_manager.py` - Background task management
- `src/autonomous_agent.py` - Autonomous agent and critic system
- `src/deep_research_agent.py` - **NEW**: Deep research system
- `src/terminal.py` - Interactive terminal interface
- `src/split_terminal.py` - Split-screen curses UI

### Data Storage

```
data/
├── agent_state/           # Agent state and instructions
├── research_state/        # Research sessions and results (NEW)
├── task_data/            # Task outputs and history
└── workspace/            # Code execution workspace
```

## Features in Detail

### Autonomous Code Execution

The agent can write and execute code to solve problems:

```bash
do Calculate compound interest on $10000 at 5% for 10 years
do Fetch latest news from an API and summarize
do Create a script to organize files by extension
```

### Bing Grounding

Web search with Bing grounding for real-time information:

```bash
search Latest developments in quantum computing
search Current stock price of NVIDIA
```

### Scheduled Tasks

Configure recurring tasks in `default_tasks.json` or add at runtime:

```bash
schedule daily-news 3600 "Summarize today's top tech news"
```

### Multi-Model Support

Switch between models on the fly:

```bash
models              # List available models
model gpt-5         # Switch to GPT-5
model gpt-4o        # Switch to GPT-4o
```

## Documentation

- **Deep Research**: See [DEEP_RESEARCH_README.md](DEEP_RESEARCH_README.md) for detailed documentation
- **Examples**: Check `examples_research.py` for complete code examples
- **Tests**: Run `python test_research_basic.py` to verify installation

## Requirements

- Python 3.8+
- Azure OpenAI API access
- Required packages (see `requirements.txt`)

## Environment Variables

Required in `.env` file:

```
# Model endpoints and keys
AZURE_OAI_GPT5_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OAI_GPT5_API_KEY=your_api_key

# Optional: Bing grounding
AZURE_AI_WUS_PROJECT_ENDPOINT=your_endpoint
AZURE_AI_WUS_API_KEY=your_key
AZURE_AI_WUS_BING_RESOURCE_NAME=your_bing_resource
```

## Project Structure

```
crapbot/
├── src/
│   ├── agent.py                    # Main entry point
│   ├── ai_client.py                # AI client wrapper
│   ├── autonomous_agent.py         # Autonomous agents
│   ├── deep_research_agent.py      # Deep research system (NEW)
│   ├── tools.py                    # Tool definitions
│   ├── task_manager.py             # Task management
│   ├── terminal.py                 # Terminal UI
│   └── split_terminal.py           # Split-screen UI
├── data/                           # Runtime data
├── examples_research.py            # Research examples (NEW)
├── test_research_basic.py          # Basic tests (NEW)
├── default_tasks.json              # Default task config
├── requirements.txt                # Python dependencies
├── README.md                       # This file
└── DEEP_RESEARCH_README.md         # Deep research docs (NEW)
```

## Contributing

Contributions are welcome! Areas for improvement:
- Additional research methods and tools
- Research quality metrics
- Multi-agent collaboration features
- Template library for common research problems

## License

[Add your license here]

## Contact

[Add your contact information]

---

## What's New

### Deep Research System (Latest)

- ✨ Autonomous research planning with problem-type adaptation
- 🔍 Multi-method research (web search, code, analysis)
- 🎯 Critical review with quality scoring
- 💬 Researcher-reviewer discussion system
- 📈 Automatic iteration for quality improvement
- 💾 Research session persistence
- 📚 Complete documentation and examples

### Previous Features

- Autonomous code execution (Python, JS, PowerShell)
- Background task system with scheduling
- Split-screen UI with agent and critic
- Multi-model support
- Tool system with 20+ tools
- Bing grounding for web search
