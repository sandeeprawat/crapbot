"""Deep Research Agent with autonomous planning, research, and self-adaptation capabilities.

This module implements a sophisticated research agent that can:
- Autonomously plan research strategies based on the problem
- Adapt its approach based on problem characteristics
- Use various tools (code, web search, etc.) for thorough research
- Iterate and refine its research based on findings
- Collaborate with a reviewer to validate and improve results
"""
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from ai_client import get_ai_client
from config import DATA_DIR


# Research state storage
_RESEARCH_STATE_DIR = os.path.join(DATA_DIR, "research_state")
os.makedirs(_RESEARCH_STATE_DIR, exist_ok=True)


class ResearchPlan:
    """Represents a research plan with steps and progress tracking."""
    
    def __init__(self, problem: str, steps: List[Dict[str, Any]] = None):
        self.problem = problem
        self.steps = steps or []
        self.current_step = 0
        self.findings = []
        self.iterations = 0
        self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem": self.problem,
            "steps": self.steps,
            "current_step": self.current_step,
            "findings": self.findings,
            "iterations": self.iterations,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResearchPlan':
        plan = cls(data["problem"], data.get("steps", []))
        plan.current_step = data.get("current_step", 0)
        plan.findings = data.get("findings", [])
        plan.iterations = data.get("iterations", 0)
        plan.created_at = data.get("created_at", datetime.now().isoformat())
        return plan


class DeepResearchAgent:
    """An autonomous research agent that can plan, research, and adapt its approach."""
    
    def __init__(self, on_output: Callable[[str], None] = None):
        """
        Args:
            on_output: Callback to send output/progress updates to the UI
        """
        self.ai = get_ai_client()
        self.on_output = on_output or (lambda text: None)
        self.current_plan: Optional[ResearchPlan] = None
        self.max_iterations = 5
        self.research_id = None
    
    def research(self, problem: str, context: str = "") -> Dict[str, Any]:
        """
        Conduct deep research on the given problem.
        
        Args:
            problem: The problem or question to research
            context: Additional context or constraints
            
        Returns:
            Dict containing research results, findings, and final answer
        """
        self.research_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.on_output(f"\n{'='*80}")
        self.on_output(f"DEEP RESEARCH SESSION: {self.research_id}")
        self.on_output(f"{'='*80}")
        self.on_output(f"\nProblem: {problem}")
        if context:
            self.on_output(f"Context: {context}")
        self.on_output("\n")
        
        # Phase 1: Analyze problem and create initial plan
        self.on_output("[Phase 1] Analyzing problem and creating research plan...")
        self.current_plan = self._create_research_plan(problem, context)
        self._save_state()
        
        # Phase 2: Execute research plan with iterations
        self.on_output(f"\n[Phase 2] Executing research plan ({len(self.current_plan.steps)} steps)...")
        research_results = self._execute_research_plan()
        
        # Phase 3: Synthesize findings
        self.on_output("\n[Phase 3] Synthesizing findings into final answer...")
        final_answer = self._synthesize_findings(research_results)
        
        result = {
            "problem": problem,
            "context": context,
            "plan": self.current_plan.to_dict(),
            "research_results": research_results,
            "final_answer": final_answer,
            "research_id": self.research_id,
            "completed_at": datetime.now().isoformat()
        }
        
        self._save_research_results(result)
        return result
    
    def _create_research_plan(self, problem: str, context: str) -> ResearchPlan:
        """Analyze the problem and create a tailored research plan."""
        planning_prompt = f"""You are a research planning expert. Analyze the following problem and create a detailed research plan.

Problem: {problem}
{f'Context: {context}' if context else ''}

Your task:
1. Identify the type of problem (e.g., financial analysis, philosophical inquiry, technical research, etc.)
2. Determine the best research approach for this specific problem type
3. Create a step-by-step research plan with 3-5 concrete steps
4. For each step, specify:
   - What to research or investigate
   - Which tools or methods to use (web search, code analysis, data gathering, etc.)
   - Expected outcomes

Return your plan in JSON format:
{{
  "problem_type": "...",
  "research_approach": "...",
  "steps": [
    {{
      "step_number": 1,
      "description": "...",
      "methods": ["web_search", "code_analysis", etc.],
      "expected_outcome": "..."
    }},
    ...
  ]
}}

Be specific and actionable. Adapt your plan to the problem type."""
        
        response = self.ai.chat(
            planning_prompt,
            system_prompt="You are a strategic research planner. Create comprehensive, adaptive research plans.",
            use_tools=False
        )
        
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                plan_data = json.loads(response[json_start:json_end])
                plan = ResearchPlan(problem, plan_data.get("steps", []))
                
                self.on_output(f"\nProblem Type: {plan_data.get('problem_type', 'Unknown')}")
                self.on_output(f"Research Approach: {plan_data.get('research_approach', 'Standard')}")
                self.on_output(f"\nResearch Plan ({len(plan.steps)} steps):")
                for step in plan.steps:
                    self.on_output(f"  {step['step_number']}. {step['description']}")
                    self.on_output(f"     Methods: {', '.join(step.get('methods', []))}")
                
                return plan
        except Exception as e:
            self.on_output(f"Warning: Could not parse plan JSON: {e}")
        
        # Fallback to basic plan
        return ResearchPlan(problem, [
            {
                "step_number": 1,
                "description": "Research background information",
                "methods": ["web_search"],
                "expected_outcome": "Background context"
            },
            {
                "step_number": 2,
                "description": "Analyze specific aspects",
                "methods": ["web_search", "code_analysis"],
                "expected_outcome": "Detailed findings"
            },
            {
                "step_number": 3,
                "description": "Synthesize conclusions",
                "methods": ["analysis"],
                "expected_outcome": "Final answer"
            }
        ])
    
    def _execute_research_plan(self) -> List[Dict[str, Any]]:
        """Execute the research plan step by step with iteration support."""
        results = []
        
        for step in self.current_plan.steps:
            self.on_output(f"\n--- Step {step['step_number']}: {step['description']} ---")
            
            step_result = self._execute_research_step(step)
            results.append(step_result)
            
            self.current_plan.findings.append(step_result)
            self.current_plan.current_step += 1
            self._save_state()
            
            # Check if we should iterate on this step
            if self._should_iterate(step, step_result):
                self.on_output("\n[Iteration] Refining research for this step...")
                refined_result = self._refine_research_step(step, step_result)
                results[-1] = refined_result
                self.current_plan.findings[-1] = refined_result
            
            self.current_plan.iterations += 1
        
        return results
    
    def _execute_research_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single research step using appropriate methods."""
        methods = step.get('methods', [])
        findings = []
        
        # Execute based on methods specified
        if 'web_search' in methods:
            search_result = self._perform_web_search(step)
            findings.append({"method": "web_search", "result": search_result})
            self.on_output(f"[Web Search] {search_result[:300]}...")
        
        if 'code_analysis' in methods or 'code' in methods:
            code_result = self._perform_code_analysis(step)
            findings.append({"method": "code_analysis", "result": code_result})
            self.on_output(f"[Code Analysis] {code_result[:300]}...")
        
        if 'data_gathering' in methods:
            data_result = self._gather_data(step)
            findings.append({"method": "data_gathering", "result": data_result})
            self.on_output(f"[Data Gathering] {data_result[:300]}...")
        
        # If no specific method or 'analysis' method, use AI reasoning
        if not findings or 'analysis' in methods:
            context = "\n\n".join([f"{f['method']}: {f['result']}" for f in findings])
            analysis = self._perform_analysis(step, context)
            findings.append({"method": "analysis", "result": analysis})
            self.on_output(f"[Analysis] {analysis[:300]}...")
        
        return {
            "step": step['step_number'],
            "description": step['description'],
            "findings": findings,
            "timestamp": datetime.now().isoformat()
        }
    
    def _perform_web_search(self, step: Dict[str, Any]) -> str:
        """Perform web search using Bing grounding or available search tools."""
        search_query = step['description']
        
        # Use AI to generate better search query
        query_prompt = f"""Generate a focused search query for: {search_query}

Problem context: {self.current_plan.problem}

Return only the search query, optimized for getting the most relevant results."""
        
        optimized_query = self.ai.chat(
            query_prompt,
            system_prompt="You are a search query expert. Generate precise search queries.",
            use_tools=False
        ).strip()
        
        self.on_output(f"  Searching: {optimized_query}")
        
        # Perform search
        search_results = self.ai.search(optimized_query)
        
        return search_results
    
    def _perform_code_analysis(self, step: Dict[str, Any]) -> str:
        """Perform code analysis or execute code for the research step."""
        code_prompt = f"""You need to perform code analysis or write code to help with this research step:

Step: {step['description']}
Problem: {self.current_plan.problem}

Determine if code execution would help answer this step. If yes:
1. Write Python code to analyze data, make calculations, or gather information
2. Execute the code
3. Provide the results

If code won't help, explain why and provide alternative insights."""
        
        result = self.ai.chat(
            code_prompt,
            system_prompt="You are a data analyst and programmer. Use code to solve problems.",
            use_tools=True  # This enables code execution tools
        )
        
        return result
    
    def _gather_data(self, step: Dict[str, Any]) -> str:
        """Gather data through various means."""
        data_prompt = f"""Gather relevant data for this research step:

Step: {step['description']}
Problem: {self.current_plan.problem}

Use available tools to gather data. Be thorough and specific."""
        
        result = self.ai.chat(
            data_prompt,
            system_prompt="You are a data researcher. Gather comprehensive information.",
            use_tools=True
        )
        
        return result
    
    def _perform_analysis(self, step: Dict[str, Any], context: str) -> str:
        """Perform analytical reasoning on gathered information."""
        analysis_prompt = f"""Analyze the information gathered for this research step:

Step: {step['description']}
Problem: {self.current_plan.problem}

Information gathered:
{context}

Provide deep analysis and insights. Be critical and thorough."""
        
        result = self.ai.chat(
            analysis_prompt,
            system_prompt="You are an analytical expert. Provide deep insights and critical analysis.",
            use_tools=False
        )
        
        return result
    
    def _should_iterate(self, step: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """Determine if we should iterate on this step for better results."""
        if self.current_plan.iterations >= self.max_iterations:
            return False
        
        # Use AI to evaluate if iteration would help
        eval_prompt = f"""Evaluate if this research step needs refinement:

Step: {step['description']}
Result: {json.dumps(result, indent=2)[:1000]}

Are the findings sufficient and high-quality? Answer with YES or NO, followed by brief explanation."""
        
        response = self.ai.chat(
            eval_prompt,
            system_prompt="You are a research quality evaluator.",
            use_tools=False
        )
        
        return "no" in response.lower()[:50]
    
    def _refine_research_step(self, step: Dict[str, Any], previous_result: Dict[str, Any]) -> Dict[str, Any]:
        """Refine and improve research for a step."""
        refine_prompt = f"""The previous research for this step needs improvement:

Step: {step['description']}
Previous findings: {json.dumps(previous_result, indent=2)[:1000]}

Conduct additional research to fill gaps, verify information, or explore alternative angles.
Be more thorough this time."""
        
        refinement = self.ai.chat(
            refine_prompt,
            system_prompt="You are a thorough researcher. Leave no stone unturned.",
            use_tools=True
        )
        
        # Combine with previous findings
        refined_result = previous_result.copy()
        refined_result['findings'].append({
            "method": "refinement",
            "result": refinement
        })
        
        return refined_result
    
    def _synthesize_findings(self, research_results: List[Dict[str, Any]]) -> str:
        """Synthesize all research findings into a comprehensive answer."""
        findings_text = "\n\n".join([
            f"Step {r['step']}: {r['description']}\n" +
            "\n".join([f"  - {f['method']}: {f['result'][:500]}..." for f in r['findings']])
            for r in research_results
        ])
        
        synthesis_prompt = f"""Synthesize all research findings into a comprehensive, well-reasoned answer:

Original Problem: {self.current_plan.problem}

Research Findings:
{findings_text}

Provide:
1. A clear, direct answer to the problem
2. Supporting evidence from the research
3. Key insights and conclusions
4. Any limitations or caveats

Be thorough but concise. Format the answer in a professional, readable manner."""
        
        final_answer = self.ai.chat(
            synthesis_prompt,
            system_prompt="You are an expert at synthesizing research into clear conclusions.",
            use_tools=False
        )
        
        self.on_output(f"\n{'-'*80}")
        self.on_output("FINAL ANSWER:")
        self.on_output(f"{'-'*80}")
        self.on_output(final_answer)
        
        return final_answer
    
    def _save_state(self):
        """Save current research state to disk."""
        if not self.research_id or not self.current_plan:
            return
        
        state_file = os.path.join(_RESEARCH_STATE_DIR, f"{self.research_id}_state.json")
        try:
            with open(state_file, 'w') as f:
                json.dump(self.current_plan.to_dict(), f, indent=2)
        except Exception:
            pass
    
    def _save_research_results(self, results: Dict[str, Any]):
        """Save final research results to disk."""
        results_file = os.path.join(_RESEARCH_STATE_DIR, f"{self.research_id}_results.json")
        try:
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            self.on_output(f"\nResults saved to: {results_file}")
        except Exception as e:
            self.on_output(f"Warning: Could not save results: {e}")


class ResearchReviewer:
    """A critical reviewer that evaluates research and provides feedback."""
    
    def __init__(self, on_output: Callable[[str], None] = None):
        self.ai = get_ai_client()
        self.on_output = on_output or (lambda text: None)
        self.review_history = []
    
    def review(self, research_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review research results and provide critical feedback.
        
        Args:
            research_result: The complete research result to review
            
        Returns:
            Dict containing review feedback, score, and suggestions
        """
        self.on_output(f"\n{'='*80}")
        self.on_output("RESEARCH REVIEW")
        self.on_output(f"{'='*80}\n")
        
        problem = research_result.get('problem', 'Unknown')
        final_answer = research_result.get('final_answer', '')
        plan = research_result.get('plan', {})
        
        review_prompt = f"""You are a critical research reviewer. Thoroughly review this research:

Problem: {problem}

Research Plan:
{json.dumps(plan.get('steps', []), indent=2)}

Final Answer:
{final_answer}

Provide a comprehensive review covering:
1. Quality Score (1-10): Rate the overall quality
2. Strengths: What was done well?
3. Weaknesses: What gaps or issues exist?
4. Accuracy: Is the information accurate and well-supported?
5. Completeness: Is anything missing?
6. Suggestions: How can this be improved?

Be honest and constructive. Don't hold back on criticism if deserved."""
        
        review_response = self.ai.chat(
            review_prompt,
            system_prompt="You are a rigorous research reviewer. Be thorough and critical.",
            use_tools=False
        )
        
        self.on_output(review_response)
        
        # Parse score
        score = self._extract_score(review_response)
        
        review_result = {
            "review_text": review_response,
            "score": score,
            "timestamp": datetime.now().isoformat()
        }
        
        self.review_history.append(review_result)
        return review_result
    
    def _extract_score(self, review_text: str) -> int:
        """Extract quality score from review text."""
        import re
        # Look for patterns like "Score: 7" or "Quality Score (1-10): 8"
        patterns = [
            r'score[:\s]+(\d+)',
            r'(\d+)\s*/\s*10',
            r'quality[:\s]+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, review_text.lower())
            if match:
                try:
                    score = int(match.group(1))
                    if 1 <= score <= 10:
                        return score
                except:
                    pass
        
        return 5  # Default middle score
    
    def discuss_with_researcher(self, research_agent: DeepResearchAgent, 
                               review: Dict[str, Any], max_rounds: int = 3) -> Dict[str, Any]:
        """
        Have a discussion with the researcher to improve the answer.
        
        Args:
            research_agent: The research agent to discuss with
            review: The review feedback
            max_rounds: Maximum discussion rounds
            
        Returns:
            Dict containing the final agreed-upon answer and discussion history
        """
        self.on_output(f"\n{'='*80}")
        self.on_output("RESEARCHER-REVIEWER DISCUSSION")
        self.on_output(f"{'='*80}\n")
        
        discussion_history = []
        current_answer = research_agent.current_plan.findings[-1] if research_agent.current_plan.findings else {}
        
        for round_num in range(1, max_rounds + 1):
            self.on_output(f"\n--- Discussion Round {round_num} ---\n")
            
            # Reviewer provides specific feedback
            feedback = self._generate_feedback(current_answer, review, round_num)
            self.on_output(f"[Reviewer] {feedback}\n")
            discussion_history.append({"role": "reviewer", "content": feedback})
            
            # Researcher responds and refines
            response = self._researcher_response(research_agent, feedback, current_answer)
            self.on_output(f"[Researcher] {response}\n")
            discussion_history.append({"role": "researcher", "content": response})
            
            # Check if agreement is reached
            if self._check_agreement(feedback, response):
                self.on_output("\n[Agreement Reached] Both parties agree on the answer.")
                break
        
        return {
            "final_answer": response,
            "discussion_history": discussion_history,
            "rounds": round_num,
            "agreement_reached": round_num < max_rounds
        }
    
    def _generate_feedback(self, answer: Any, review: Dict[str, Any], round_num: int) -> str:
        """Generate specific feedback for the researcher."""
        feedback_prompt = f"""Based on your review, provide specific, actionable feedback for the researcher:

Review: {review.get('review_text', '')[:1000]}
Current Answer: {str(answer)[:500]}
Discussion Round: {round_num}

Give 2-3 specific points the researcher should address to improve the answer."""
        
        return self.ai.chat(
            feedback_prompt,
            system_prompt="You are a constructive reviewer. Give specific, actionable feedback.",
            use_tools=False
        )
    
    def _researcher_response(self, research_agent: DeepResearchAgent, 
                           feedback: str, current_answer: Any) -> str:
        """Get researcher's response to feedback."""
        response_prompt = f"""You received this feedback on your research:

Feedback: {feedback}

Original Problem: {research_agent.current_plan.problem if research_agent.current_plan else 'Unknown'}
Current Answer: {str(current_answer)[:500]}

Respond to the feedback and provide an improved answer if needed. Be specific about what you're changing and why."""
        
        return research_agent.ai.chat(
            response_prompt,
            system_prompt="You are a researcher responding to peer review. Be receptive but defend your work when appropriate.",
            use_tools=True
        )
    
    def _check_agreement(self, feedback: str, response: str) -> bool:
        """Check if reviewer and researcher have reached agreement."""
        # Simple heuristic: look for agreement keywords
        agreement_keywords = ['agree', 'acceptable', 'satisfactory', 'good enough', 'sounds good']
        response_lower = response.lower()
        return any(keyword in response_lower for keyword in agreement_keywords)


class ResearchOrchestrator:
    """Orchestrates the research-review cycle with autonomous discussion."""
    
    def __init__(self, on_output: Callable[[str], None] = None):
        self.on_output = on_output or print
        self.research_agent = DeepResearchAgent(on_output=self.on_output)
        self.reviewer = ResearchReviewer(on_output=self.on_output)
    
    def conduct_research(self, problem: str, context: str = "", 
                        min_score: int = 7, max_attempts: int = 2) -> Dict[str, Any]:
        """
        Conduct complete research with review and iteration.
        
        Args:
            problem: The problem to research
            context: Additional context
            min_score: Minimum acceptable review score (1-10)
            max_attempts: Maximum research attempts
            
        Returns:
            Dict with final research results, reviews, and discussions
        """
        self.on_output(f"\n{'#'*80}")
        self.on_output(f"# DEEP RESEARCH SESSION")
        self.on_output(f"# Problem: {problem}")
        self.on_output(f"{'#'*80}\n")
        
        all_attempts = []
        
        for attempt in range(1, max_attempts + 1):
            self.on_output(f"\n{'='*80}")
            self.on_output(f"RESEARCH ATTEMPT {attempt}/{max_attempts}")
            self.on_output(f"{'='*80}\n")
            
            # Conduct research
            research_result = self.research_agent.research(problem, context)
            
            # Review research
            review = self.reviewer.review(research_result)
            
            attempt_data = {
                "attempt": attempt,
                "research": research_result,
                "review": review
            }
            
            # Check if score is acceptable
            if review['score'] >= min_score:
                self.on_output(f"\n✓ Score {review['score']}/10 meets threshold. Research accepted.")
                attempt_data['accepted'] = True
                all_attempts.append(attempt_data)
                break
            else:
                self.on_output(f"\n✗ Score {review['score']}/10 below threshold {min_score}. Discussing improvements...")
                
                # Have discussion to improve
                discussion = self.reviewer.discuss_with_researcher(
                    self.research_agent, review, max_rounds=2
                )
                attempt_data['discussion'] = discussion
                attempt_data['accepted'] = False
                all_attempts.append(attempt_data)
                
                # Update context for next attempt
                context += f"\n\nPrevious attempt feedback: {review['review_text'][:300]}"
        
        final_result = {
            "problem": problem,
            "attempts": all_attempts,
            "final_accepted": all_attempts[-1].get('accepted', False),
            "final_score": all_attempts[-1]['review']['score'],
            "completed_at": datetime.now().isoformat()
        }
        
        self.on_output(f"\n{'#'*80}")
        self.on_output(f"# RESEARCH SESSION COMPLETE")
        self.on_output(f"# Final Score: {final_result['final_score']}/10")
        self.on_output(f"# Status: {'ACCEPTED' if final_result['final_accepted'] else 'NEEDS MORE WORK'}")
        self.on_output(f"{'#'*80}\n")
        
        return final_result


def run_deep_research(problem: str, context: str = "", on_output: Callable[[str], None] = None) -> Dict[str, Any]:
    """
    Convenience function to run a complete deep research session.
    
    Args:
        problem: The problem or question to research
        context: Additional context or constraints
        on_output: Optional callback for progress updates
        
    Returns:
        Complete research results with reviews and discussions
    """
    orchestrator = ResearchOrchestrator(on_output=on_output)
    return orchestrator.conduct_research(problem, context)
