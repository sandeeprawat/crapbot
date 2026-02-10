"""Example usage of the Deep Research Agent.

This script demonstrates how to use the deep research system for various types of problems.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from deep_research_agent import run_deep_research


def example_stock_research():
    """Example: Research stocks for investment."""
    print("\n" + "="*80)
    print("EXAMPLE 1: Stock Research")
    print("="*80 + "\n")
    
    problem = """Identify 3-5 stocks that could make good returns in the next 3-6 months.
    
Focus on:
- Technology and AI companies
- Recent performance and trends
- Market conditions and upcoming catalysts
- Risk factors

Provide specific stock symbols and reasoning."""
    
    result = run_deep_research(problem)
    
    print("\n\nRESEARCH COMPLETED")
    print(f"Final Score: {result['final_score']}/10")
    print(f"Status: {'Accepted' if result['final_accepted'] else 'Needs improvement'}")


def example_philosophical_concept():
    """Example: Generate a novel philosophical concept."""
    print("\n" + "="*80)
    print("EXAMPLE 2: Novel Philosophical Concept")
    print("="*80 + "\n")
    
    problem = """Come up with a novel philosophical concept that has not been explicitly discussed or named before.

Requirements:
- Must be genuinely new (or at least a fresh synthesis)
- Should address contemporary issues or timeless questions
- Provide a clear definition and explanation
- Show how it relates to existing philosophical traditions
- Give practical examples of the concept in action"""
    
    result = run_deep_research(problem)
    
    print("\n\nRESEARCH COMPLETED")
    print(f"Final Score: {result['final_score']}/10")
    print(f"Status: {'Accepted' if result['final_accepted'] else 'Needs improvement'}")


def example_technical_problem():
    """Example: Technical problem solving."""
    print("\n" + "="*80)
    print("EXAMPLE 3: Technical Problem Solving")
    print("="*80 + "\n")
    
    problem = """Design an efficient algorithm for detecting anomalies in time-series data.

Requirements:
- Must handle streaming data
- Low computational complexity
- Adaptive to changing patterns
- Minimal false positives
- Include implementation considerations"""
    
    result = run_deep_research(problem)
    
    print("\n\nRESEARCH COMPLETED")
    print(f"Final Score: {result['final_score']}/10")
    print(f"Status: {'Accepted' if result['final_accepted'] else 'Needs improvement'}")


def example_market_analysis():
    """Example: Market trend analysis."""
    print("\n" + "="*80)
    print("EXAMPLE 4: Market Trend Analysis")
    print("="*80 + "\n")
    
    problem = """Analyze the current trends in renewable energy sector.

Focus on:
- Which technologies are gaining traction
- Market size and growth projections
- Key players and competitive landscape
- Investment opportunities
- Regulatory and policy impacts"""
    
    result = run_deep_research(problem)
    
    print("\n\nRESEARCH COMPLETED")
    print(f"Final Score: {result['final_score']}/10")
    print(f"Status: {'Accepted' if result['final_accepted'] else 'Needs improvement'}")


def main():
    """Run example demonstrations."""
    print("\n" + "#"*80)
    print("# DEEP RESEARCH AGENT - EXAMPLES")
    print("#"*80)
    print("\nThis script demonstrates the Deep Research Agent with various problem types.")
    print("Each example will:")
    print("  1. Create an adaptive research plan")
    print("  2. Execute research using multiple methods (web search, code, analysis)")
    print("  3. Get critical review from a reviewer agent")
    print("  4. Iterate if needed to improve quality")
    print("\nNote: These examples may take several minutes each.\n")
    
    choice = input("Select example (1-4, or 'all'): ").strip()
    
    if choice == '1':
        example_stock_research()
    elif choice == '2':
        example_philosophical_concept()
    elif choice == '3':
        example_technical_problem()
    elif choice == '4':
        example_market_analysis()
    elif choice.lower() == 'all':
        example_stock_research()
        example_philosophical_concept()
        example_technical_problem()
        example_market_analysis()
    else:
        print("Invalid choice. Please run again and select 1-4 or 'all'.")


if __name__ == "__main__":
    main()
