#!/usr/bin/env python3
"""Test multi-line input functionality for Agent/Critic topic."""

import os
import sys
import tempfile


def get_multiline_input_logic(file_path: str) -> str:
    """Simulate the logic from get_multiline_input without importing the module."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Filter out comment lines and strip trailing whitespace
    content_lines = [line.rstrip() for line in lines if not line.strip().startswith('#')]
    content = '\n'.join(content_lines).strip()
    
    return content


def test_multiline_input_basic():
    """Test basic multi-line input with simulated editor content."""
    print("Test 1: Basic multi-line input")
    
    # Create a temporary file with test content
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tf:
        temp_path = tf.name
        tf.write("Line 1\n")
        tf.write("Line 2\n")
        tf.write("Line 3\n")
    
    try:
        content = get_multiline_input_logic(temp_path)
        assert content == "Line 1\nLine 2\nLine 3", f"Expected 3 lines, got: {content}"
        print("✓ Basic multi-line input works")
    finally:
        os.unlink(temp_path)


def test_multiline_input_with_comments():
    """Test multi-line input with comment filtering."""
    print("\nTest 2: Multi-line input with comment filtering")
    
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tf:
        temp_path = tf.name
        tf.write("Line 1\n")
        tf.write("# This is a comment\n")
        tf.write("Line 2\n")
        tf.write("#Another comment\n")
        tf.write("Line 3\n")
        tf.write("  # Indented comment\n")
    
    try:
        content = get_multiline_input_logic(temp_path)
        assert content == "Line 1\nLine 2\nLine 3", f"Expected 3 lines without comments, got: {content}"
        print("✓ Comment filtering works")
    finally:
        os.unlink(temp_path)


def test_multiline_input_empty():
    """Test multi-line input with empty content."""
    print("\nTest 3: Empty content handling")
    
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tf:
        temp_path = tf.name
        tf.write("# Only comments\n")
        tf.write("# Nothing else\n")
    
    try:
        content = get_multiline_input_logic(temp_path)
        assert content == "", f"Expected empty string, got: {content}"
        print("✓ Empty content handling works")
    finally:
        os.unlink(temp_path)


def test_multiline_input_whitespace():
    """Test multi-line input with various whitespace."""
    print("\nTest 4: Whitespace handling")
    
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tf:
        temp_path = tf.name
        tf.write("Line 1\n")
        tf.write("\n")
        tf.write("Line 2\n")
        tf.write("   \n")
        tf.write("Line 3\n")
    
    try:
        content = get_multiline_input_logic(temp_path)
        # Should preserve empty lines but strip trailing whitespace from each line
        expected = "Line 1\n\nLine 2\n\nLine 3"
        assert content == expected, f"Expected:\n{expected}\n\nGot:\n{content}"
        print("✓ Whitespace handling works")
    finally:
        os.unlink(temp_path)


def test_multiline_topic_example():
    """Test with a realistic topic example."""
    print("\nTest 5: Realistic topic example")
    
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tf:
        temp_path = tf.name
        tf.write("# Topic: AI Safety and Ethics\n")
        tf.write("Discuss the implications of advanced AI systems on society.\n")
        tf.write("\n")
        tf.write("Key points to explore:\n")
        tf.write("1. Alignment problem\n")
        tf.write("2. Interpretability and transparency\n")
        tf.write("3. Economic and social impacts\n")
        tf.write("# Focus on practical solutions\n")
    
    try:
        content = get_multiline_input_logic(temp_path)
        expected_lines = [
            "Discuss the implications of advanced AI systems on society.",
            "",
            "Key points to explore:",
            "1. Alignment problem",
            "2. Interpretability and transparency",
            "3. Economic and social impacts"
        ]
        expected = '\n'.join(expected_lines)
        assert content == expected, f"Expected:\n{expected}\n\nGot:\n{content}"
        print("✓ Realistic topic handling works")
    finally:
        os.unlink(temp_path)


if __name__ == '__main__':
    print("Testing multi-line input functionality\n" + "="*50)
    
    try:
        test_multiline_input_basic()
        test_multiline_input_with_comments()
        test_multiline_input_empty()
        test_multiline_input_whitespace()
        test_multiline_topic_example()
        
        print("\n" + "="*50)
        print("All tests passed! ✓")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
