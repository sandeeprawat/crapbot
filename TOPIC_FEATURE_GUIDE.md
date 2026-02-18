# Multi-Line Topic Input Feature

## Overview

This feature allows you to provide multi-line text input to the Agent/Critic session in CrapBot's split-screen mode. This is useful for:

- Providing detailed research topics
- Setting complex discussion themes
- Giving background context for the agents
- Defining constraints or guidelines

## Usage

### Quick Start

1. Start CrapBot in split-screen mode:
   ```bash
   python src/agent.py
   ```

2. Type the `topic` command:
   ```
   [You] > topic
   ```

3. The system will open your text editor (nano by default)

4. Enter your multi-line topic. For example:
   ```
   # Topic: Climate Change Solutions

   Discuss practical solutions to climate change, focusing on:

   1. Renewable energy transition strategies
   2. Carbon capture technologies
   3. Policy recommendations for governments
   4. Individual actions with measurable impact

   Consider both immediate actions and long-term planning.
   ```

5. Save and close the editor (Ctrl+X in nano, :wq in vim)

6. The topic will be added to both Agent and Critic instructions

## Features

### Comment Support

Lines starting with `#` are treated as comments and will be ignored:

```
# This is a comment - won't be included
This will be included in the topic
# Another comment
This will also be included
```

### Editor Configuration

Set your preferred editor using the `EDITOR` environment variable:

```bash
# Use vim
export EDITOR=vim
python src/agent.py

# Use emacs
export EDITOR=emacs
python src/agent.py

# Use VS Code (waits for file to close)
export EDITOR="code --wait"
python src/agent.py
```

Default editor is `nano` if EDITOR is not set.

### How It Works

1. **Suspends Curses UI**: The curses terminal is temporarily suspended
2. **Opens Editor**: Your configured editor opens with a template
3. **Processes Input**: Content is read, comments filtered out
4. **Updates Instructions**: Topic is prepended to Agent and Critic instructions
5. **Restores UI**: Curses terminal is restored and continues

## Examples

### Example 1: Research Topic

```
# Research Topic: Quantum Computing Applications

Explore practical applications of quantum computing in the next decade:

- Drug discovery and molecular simulation
- Financial modeling and risk analysis
- Optimization problems in logistics
- Cryptography and security implications

Focus on feasibility and timeline estimates.
```

### Example 2: Debate Topic

```
Should artificial general intelligence development be regulated?

Arguments to consider:
- Safety and existential risk
- Innovation and progress
- International coordination challenges
- Economic competitiveness

Aim for a balanced discussion with concrete proposals.
```

### Example 3: Problem-Solving

```
# Problem: Reducing food waste

Brainstorm solutions at multiple levels:

1. Consumer behavior changes
2. Supply chain improvements
3. Technology interventions
4. Policy incentives

Prioritize solutions by impact and feasibility.
```

## Tips

- **Keep it focused**: Provide clear, actionable prompts
- **Use structure**: Numbered lists and bullet points help guide discussion
- **Be specific**: Give context and constraints to get better results
- **Iterate**: You can use the `topic` command multiple times to refine the discussion
- **Clear when done**: Use `fresh` command to restart agents without the topic

## Related Commands

- `instruct <target> <text>` - Single-line instruction update
- `fresh` - Clear session and restart both agents
- `agents` - Check status of Agent and Critic
- `help` - Show all available commands

## Testing

Run the included tests to verify functionality:

```bash
# Run unit tests
python test_multiline_input.py

# Run demonstration
python demo_topic_feature.py
```

## Troubleshooting

### Editor doesn't open

- Check that your EDITOR is installed and in PATH
- Try setting EDITOR explicitly: `export EDITOR=nano`
- Default fallback is `nano` - ensure it's installed

### Terminal gets corrupted

- The curses UI should automatically restore
- If not, use `reset` command in your shell
- Or restart the application

### Topic not applied

- Make sure agents are running (use `agents` command to check)
- Topic is prepended to existing instructions
- Use `instruct agent` or `instruct critic` to view current instructions

### Comments not filtered

- Make sure comment lines start with `#` at the beginning (after stripping whitespace)
- Example: `# This is a comment` ✓
- Example: `This is not # a comment` ✗

## Implementation Details

- **File**: `src/split_terminal.py`
- **Function**: `get_multiline_input()` - Handles editor interaction
- **Command**: `cmd_topic()` - Integrates with split terminal
- **Safety**: Proper cleanup of temporary files
- **Error Handling**: Graceful fallback on errors

## Future Enhancements

Possible improvements for future versions:

- [ ] Support for loading topics from files
- [ ] Topic history and recall
- [ ] Topic templates library
- [ ] Integration with web UI
- [ ] Save/load topic sessions

## Contributing

If you find issues or have suggestions:

1. Open an issue on GitHub
2. Provide example use case
3. Include steps to reproduce any problems
4. Suggest improvements or alternatives
