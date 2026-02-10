"""Simple test to verify deep research agent can be imported and basic structure works."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from deep_research_agent import (
        ResearchPlan,
        DeepResearchAgent,
        ResearchReviewer,
        ResearchOrchestrator,
        run_deep_research
    )
    print("✓ All classes imported successfully")
    
    # Test ResearchPlan
    plan = ResearchPlan("Test problem")
    plan.steps = [{"step_number": 1, "description": "Test step"}]
    plan_dict = plan.to_dict()
    print(f"✓ ResearchPlan works: {plan_dict['problem']}")
    
    # Test ResearchPlan.from_dict
    restored_plan = ResearchPlan.from_dict(plan_dict)
    print(f"✓ ResearchPlan.from_dict works: {restored_plan.problem}")
    
    # Test agent creation
    agent = DeepResearchAgent(on_output=lambda x: None)
    print("✓ DeepResearchAgent created")
    
    # Test reviewer creation
    reviewer = ResearchReviewer(on_output=lambda x: None)
    print("✓ ResearchReviewer created")
    
    # Test orchestrator creation
    orchestrator = ResearchOrchestrator(on_output=lambda x: None)
    print("✓ ResearchOrchestrator created")
    
    print("\n✓✓✓ All basic tests passed! ✓✓✓")
    print("\nNote: Full integration tests require API keys and will be done manually.")
    
except Exception as e:
    print(f"✗ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
