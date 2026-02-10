# Deep Research Agent - Documentation

## Overview

The Deep Research Agent is an autonomous AI system that can conduct thorough research on complex problems by:
- **Adaptive Planning**: Creates customized research plans based on problem type
- **Multi-Method Research**: Uses web search, code execution, and analytical reasoning
- **Critical Review**: A separate reviewer agent evaluates research quality
- **Iterative Improvement**: Automatically refines research based on feedback
- **Researcher-Reviewer Discussion**: Agents discuss and debate to reach consensus

## Architecture

### Components

1. **DeepResearchAgent**: The primary research agent
   - Analyzes problems and creates adaptive research plans
   - Executes multi-step research using various methods
   - Iterates on findings to improve quality
   - Synthesizes comprehensive answers

2. **ResearchReviewer**: The critical reviewer
   - Evaluates research quality with 1-10 scoring
   - Identifies strengths, weaknesses, and gaps
   - Provides specific, actionable feedback
   - Engages in discussion with researcher

3. **ResearchOrchestrator**: The coordination layer
   - Manages research-review cycles
   - Enforces quality thresholds
   - Handles multiple research attempts
   - Tracks complete session history

### Research Workflow

```
1. Problem Analysis → Create Adaptive Plan
2. Execute Research Plan
   ├─ Web Search (with Bing grounding)
   ├─ Code Analysis/Execution
   ├─ Data Gathering
   └─ Analytical Reasoning
3. Synthesize Findings
4. Critical Review (Quality Score)
5. If Score < Threshold:
   ├─ Researcher-Reviewer Discussion
   └─ Iterate with Improvements
6. Final Answer (with confidence score)
```

## Usage

### Command Line Interface

#### Terminal Mode
```bash
# From the CrapBot terminal
research <your problem or question>

# Examples:
research Identify stocks that could make good returns in next 3 months
research Come up with a novel philosophical concept
research Design an algorithm for anomaly detection in time-series data
```

#### Split-Screen Mode
```bash
# Same command works in split-screen mode
research <problem>
```

### Python API

```python
from deep_research_agent import run_deep_research

# Simple usage
result = run_deep_research("What are the best investment opportunities in AI?")

# With context
result = run_deep_research(
    problem="Analyze renewable energy trends",
    context="Focus on solar and wind power, next 5 years",
    on_output=print  # Optional: stream progress
)

# Access results
print(f"Score: {result['final_score']}/10")
print(f"Answer: {result['attempts'][-1]['research']['final_answer']}")
```

### Advanced Usage

```python
from deep_research_agent import ResearchOrchestrator

orchestrator = ResearchOrchestrator(on_output=print)

# Custom quality threshold and max attempts
result = orchestrator.conduct_research(
    problem="Your research question",
    context="Additional constraints or context",
    min_score=8,  # Only accept research scoring 8/10 or higher
    max_attempts=3  # Try up to 3 times to meet threshold
)
```

## Features

### 1. Adaptive Research Planning

The agent analyzes each problem and creates a customized research plan:

- **Problem Classification**: Identifies problem type (financial, philosophical, technical, etc.)
- **Method Selection**: Chooses appropriate research methods for the problem
- **Step Generation**: Creates 3-5 concrete research steps
- **Outcome Definition**: Sets clear expectations for each step

Example for stock research:
```
1. Gather current market data and trends [web_search, data_gathering]
2. Analyze company financials and performance [code_analysis, web_search]
3. Evaluate risk factors and catalysts [analysis, web_search]
```

### 2. Multi-Method Research

Each research step can use multiple methods:

- **Web Search**: Bing grounding for real-time information
- **Code Execution**: Python/JavaScript for calculations and analysis
- **Data Gathering**: API calls, file processing, etc.
- **Analytical Reasoning**: AI-powered deep thinking

### 3. Quality Iteration

Research automatically iterates to improve quality:

- Evaluates if findings are sufficient
- Identifies gaps or weak points
- Performs additional research as needed
- Maximum 5 iterations per step

### 4. Critical Review System

The reviewer provides thorough evaluation:

- **Quality Score**: 1-10 rating with justification
- **Strengths**: What was done well
- **Weaknesses**: Gaps, errors, or concerns
- **Suggestions**: Specific improvements

### 5. Researcher-Reviewer Discussion

When quality is below threshold:

1. Reviewer provides specific feedback
2. Researcher responds and refines answer
3. Up to 3 discussion rounds
4. Agreement checking to conclude

## Configuration

### Quality Thresholds

```python
# Default: min_score=7, max_attempts=2
result = orchestrator.conduct_research(
    problem="...",
    min_score=8,  # Raise the bar
    max_attempts=3  # Allow more attempts
)
```

### Output Callbacks

```python
# Stream output to custom handler
def my_output_handler(text):
    print(f"[LOG] {text}")
    # Or write to file, send to UI, etc.

result = run_deep_research("...", on_output=my_output_handler)
```

## Example Use Cases

### 1. Financial Research
```python
result = run_deep_research(
    "Identify 3-5 stocks with strong growth potential in the AI sector"
)
```

### 2. Philosophical Inquiry
```python
result = run_deep_research(
    "Develop a novel ethical framework for AI decision-making"
)
```

### 3. Technical Problem Solving
```python
result = run_deep_research(
    "Design an efficient algorithm for real-time fraud detection",
    context="Must handle 100k transactions/second with <100ms latency"
)
```

### 4. Market Analysis
```python
result = run_deep_research(
    "Analyze emerging trends in the cryptocurrency market for 2026"
)
```

## Output Format

The research result is a comprehensive dictionary:

```python
{
    "problem": "Original problem statement",
    "attempts": [
        {
            "attempt": 1,
            "research": {
                "problem": "...",
                "plan": {...},
                "research_results": [...],
                "final_answer": "Comprehensive answer",
                "research_id": "20260210_192758",
                "completed_at": "..."
            },
            "review": {
                "review_text": "Full review with feedback",
                "score": 8,
                "timestamp": "..."
            },
            "discussion": {  # If score below threshold
                "final_answer": "Refined answer",
                "discussion_history": [...],
                "rounds": 2,
                "agreement_reached": true
            },
            "accepted": true
        }
    ],
    "final_accepted": true,
    "final_score": 8,
    "completed_at": "2026-02-10T19:27:58.772Z"
}
```

## Persistence

Research state is automatically saved to `data/research_state/`:

- `{research_id}_state.json`: Current research plan and progress
- `{research_id}_results.json`: Complete research results

This allows:
- Resuming interrupted research
- Reviewing past research sessions
- Analyzing research patterns

## Tips for Best Results

1. **Be Specific**: Provide clear, focused problems
2. **Add Context**: Include constraints, preferences, or requirements
3. **Set Appropriate Thresholds**: Lower scores (6-7) for exploratory research, higher (8-9) for critical decisions
4. **Review Process**: Check the research plan before execution completes
5. **Iterate Manually**: If unhappy with results, run again with refined problem statement

## Limitations

- Research quality depends on:
  - Available data sources
  - Problem complexity
  - AI model capabilities
- Web search limited to public information
- Code execution restricted to safe operations
- Processing time: 2-10 minutes per research session

## Future Enhancements

Planned improvements:
- [ ] Parallel research paths
- [ ] Custom tool integration
- [ ] Research templates for common problems
- [ ] Multi-agent collaboration
- [ ] Research quality analytics
- [ ] Interactive research refinement

## Examples

See `examples_research.py` for complete working examples:

```bash
python examples_research.py
```

Choose from:
1. Stock research
2. Philosophical concept generation
3. Technical problem solving
4. Market trend analysis

## Troubleshooting

### Research Takes Too Long
- Reduce complexity of problem
- Lower quality threshold
- Limit context/constraints

### Low Quality Scores
- Provide more specific problem statement
- Add relevant context
- Check if problem is well-defined

### Import Errors
```bash
pip install -r requirements.txt
```

### API Rate Limits
- The system includes retry logic
- Automatic delays between requests
- Consider caching for repeated queries

## Support

For issues or questions:
1. Check documentation above
2. Review examples in `examples_research.py`
3. Run basic tests: `python test_research_basic.py`
4. Check logs in `data/research_state/`
