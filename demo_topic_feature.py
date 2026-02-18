#!/usr/bin/env python3
"""
Demonstration of the multi-line topic input feature.

This script shows how the topic command works and what it does.
"""

import tempfile
import os


def simulate_topic_input():
    """Simulate what happens when a user uses the topic command."""
    
    print("=" * 70)
    print("DEMONSTRATION: Multi-Line Topic Input for Agent/Critic Session")
    print("=" * 70)
    print()
    
    # Step 1: User invokes the topic command
    print("Step 1: User types 'topic' in the split terminal")
    print("  [You] > topic")
    print()
    
    # Step 2: System prepares to open editor
    print("Step 2: System opens editor with template")
    print("  [System] Opening editor for multi-line topic input...")
    print("  [System] The terminal will be suspended. Save and close the editor when done.")
    print()
    
    # Step 3: Show what the editor contains
    print("Step 3: Editor opens with this template:")
    print("-" * 70)
    editor_template = """# Enter your multi-line text below.
# Lines starting with # will be ignored.
# Save and close the editor when done.

"""
    print(editor_template)
    print("-" * 70)
    print()
    
    # Step 4: User enters their topic
    print("Step 4: User enters their topic (example):")
    print("-" * 70)
    example_topic = """# Topic: Exploring the Future of AI Safety

Discuss the ethical implications and technical challenges 
of advanced AI systems, focusing on:

1. Alignment problem - ensuring AI goals match human values
2. Interpretability - understanding AI decision-making
3. Scalable oversight - maintaining control as AI becomes more capable
4. Economic impacts - job displacement and wealth distribution

Consider both near-term (5 years) and long-term (20+ years) scenarios.
"""
    print(example_topic)
    print("-" * 70)
    print()
    
    # Step 5: System processes the input
    print("Step 5: User saves and closes editor, system processes input")
    
    # Simulate the filtering logic
    lines = example_topic.split('\n')
    content_lines = [line.rstrip() for line in lines if not line.strip().startswith('#')]
    filtered_content = '\n'.join(content_lines).strip()
    
    print(f"  [System] Topic received ({len(filtered_content)} characters)")
    preview = filtered_content[:200] + ("..." if len(filtered_content) > 200 else "")
    print(f"  Preview: {preview}")
    print()
    
    # Step 6: Topic is injected into agent instructions
    print("Step 6: Topic is prepended to agent instructions")
    print("  [System] Topic added to Agent instructions.")
    print("  [System] Topic added to Critic instructions.")
    print()
    
    # Step 7: Show what happens to the instructions
    print("Step 7: How instructions are modified:")
    print("-" * 70)
    print("BEFORE:")
    original_instructions = "You are a curious, thoughtful AI that thinks out loud..."
    print(f"  {original_instructions}")
    print()
    print("AFTER:")
    topic_prefix = f"Focus your discussion on this topic:\n\n{filtered_content[:100]}...\n\n"
    modified_instructions = topic_prefix + original_instructions
    print(f"  {modified_instructions[:200]}...")
    print("-" * 70)
    print()
    
    # Step 8: Agents begin discussing the topic
    print("Step 8: Agent and Critic now discuss the provided topic")
    print("  [AutoAgent] Now thinking about: AI Safety and alignment...")
    print("  [Critic] Reviewing agent's thoughts on interpretability...")
    print()
    
    print("=" * 70)
    print("Feature Benefits:")
    print("  ✓ Provides multi-line input capability")
    print("  ✓ Uses familiar text editor (EDITOR env var)")
    print("  ✓ Supports comments for notes/instructions")
    print("  ✓ Guides Agent/Critic discussion with context")
    print("  ✓ Enables complex, structured topics")
    print("=" * 70)


if __name__ == "__main__":
    simulate_topic_input()
