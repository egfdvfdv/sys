"""Orchestrator for the AGI Prompt System with caching and task queue support."""
from typing import Dict, Any, Optional, List, Union, Awaitable, Callable
import asyncio
import json
import uuid
from datetime import datetime
from functools import wraps

from .config import Config
from .agents import PromptArchitect, PromptEvaluator
from .utils import cached, TaskManager, async_task, CacheManager

class PromptOrchestrator:
    """Orchestrates the interaction between PromptArchitect and PromptEvaluator."""
    
    def __init__(self, config: Config, cache_manager: CacheManager, task_manager: TaskManager):
        """
        Initialize the orchestrator with configuration, cache manager, and task manager.
        
        Args:
            config: Configuration object
            cache_manager: CacheManager instance
            task_manager: TaskManager instance
        """
        self.config = config
        self.architect = PromptArchitect(self.config) # Assumes PromptArchitect takes config
        self.evaluator = PromptEvaluator(self.config) # Assumes PromptEvaluator takes config
        self.task_manager = task_manager
        self.cache = cache_manager
    
    @cached(ttl=86400)  # Cache for 24 hours
    async def _evaluate_prompt_cached(self, prompt: str) -> Dict[str, Any]:
        """
        Cached version of prompt evaluation.
        
        Args:
            prompt: The prompt to evaluate
            
        Returns:
            Evaluation results with score and feedback
        """
        return await self.evaluator.evaluate_prompt(prompt)
    
    async def generate_prompt(
        self, 
        requirements: str,
        max_iterations: Optional[int] = None,
        task_id: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Generate and refine a system prompt based on requirements.
        
        Args:
            requirements: Requirements for the system prompt
            max_iterations: Maximum number of refinement iterations
            task_id: Optional task ID for tracking progress
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dict containing the final prompt, score, and iteration history
        """
        max_iterations = max_iterations or self.config.MAX_ITERATIONS
        task_id = task_id or str(uuid.uuid4())
        
        # Check cache for existing results with the same requirements
        cache_key = f"prompt_gen:{hash(requirements)}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            print("🚀 Using cached prompt generation result")
            return cached_result
        
        current_prompt = await self.architect.generate_initial_prompt(requirements)
        iteration = 0
        current_run_results: List[Dict[str, Any]] = []
        
        while max_iterations is None or iteration < max_iterations:
            iteration += 1
            
            # Update task progress
            if progress_callback:
                progress_data = {
                    "task_id": task_id,
                    "iteration": iteration,
                    "status": "EVALUATING",
                    "current_score": None,
                    "timestamp": datetime.utcnow().isoformat()
                }
                progress_callback(progress_data)
            
            print(f"\n{'='*50}")
            print(f"Iteration {iteration}")
            print(f"{'='*50}")
            
            # Evaluate the current prompt with caching
            print("\nEvaluating prompt...")
            evaluation = await self._evaluate_prompt_cached(current_prompt)
            score = evaluation["score"]
            
            # Save the iteration result
            result = {
                "iteration": iteration,
                "prompt": current_prompt,
                "score": score,
                "feedback": evaluation,
                "timestamp": datetime.utcnow().isoformat()
            }
            current_run_results.append(result)
            
            # Update task progress with evaluation result
            if progress_callback:
                progress_data = {
                    "task_id": task_id,
                    "iteration": iteration,
                    "status": "EVALUATED",
                    "current_score": score,
                    "details": result, # The 'result' dict contains prompt, feedback etc.
                    "timestamp": datetime.utcnow().isoformat()
                }
                progress_callback(progress_data)
            
            print(f"Current score: {score}/1000")
            
            # Check if we've reached the target score
            if score >= self.config.MIN_ACCEPTABLE_SCORE:
                print("\n🎉 Target score achieved!")
                break
                
            if max_iterations is not None and iteration >= max_iterations:
                print("\n⚠️  Maximum iterations reached.")
                break
                
            # Refine the prompt
            print("\nRefining prompt based on feedback...")
            current_prompt = await self.architect.refine_prompt(
                current_prompt=current_prompt,
                feedback=evaluation,
                requirements=requirements
            )
        
        # Prepare final result
        final_result = {
            "task_id": task_id,
            "final_prompt": current_prompt,
            "final_score": score,
            "iterations": current_run_results,
            "requirements": requirements,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        # Cache the final result
        self.cache.set(cache_key, final_result, ttl=86400)  # Cache for 24 hours
        
        return final_result
    
    def submit_generate_prompt(self, requirements: str, max_iterations: Optional[int] = None) -> str:
        """
        Submit a prompt generation task asynchronously using Celery.
        
        Args:
            requirements: Requirements for the system prompt
            max_iterations: Maximum number of refinement iterations
            
        Returns:
            Task ID for tracking progress
        """
        # Submit Celery task and return task ID
        async_result = generate_prompt_task.delay(requirements, {'requirements': requirements, 'max_iterations': max_iterations})
        return async_result.id
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the status of an asynchronous task.
        
        Args:
            task_id: The ID of the task to check
            
        Returns:
            Dict containing task status and progress
        """
        return self.task_manager.get_task_status(task_id)
    
    def save_results(self, filepath: str, generation_output: Dict[str, Any]) -> None:
        """
        Save the prompt generation results to a JSON file.
        
        Args:
            filepath: Path to save the results file
            generation_output: The output dictionary from generate_prompt
        """
        result_data = {
            "results": generation_output["iterations"],
            "config": {
                "model": self.config.MODEL,
                "min_acceptable_score": self.config.MIN_ACCEPTABLE_SCORE,
                "max_iterations": self.config.MAX_ITERATIONS
            },
            "timestamp": datetime.utcnow().isoformat(),
            "cache_hits": getattr(self, '_cache_hits', 0),
            "cache_misses": getattr(self, '_cache_misses', 0)
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {filepath}")
    
    def clear_cache(self) -> bool:
        """
        Clear all cached data.
        
        Returns:
            bool: True if cache was cleared successfully
        """
        return self.cache.clear_all()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache hit/miss statistics
        """
        return {
            'hits': getattr(self, '_cache_hits', 0),
            'misses': getattr(self, '_cache_misses', 0)
        }


async def main():
    """Main function to run the prompt generation process."""
    # Example requirements for the AGI system prompt
    requirements = """
    Create a system prompt for an advanced AGI assistant with the following capabilities:
    - Advanced reasoning and problem-solving
    - Multi-turn conversation with context retention
    - Code generation and explanation
    - Knowledge retrieval and summarization
    - Creative writing and brainstorming
    - Ethical guidelines and safety considerations
    - Clear communication of uncertainty
    - Ability to ask clarifying questions
    - Support for multiple languages
    - Awareness of its own limitations
    """
    
    orchestrator = PromptOrchestrator()
    
    try:
        result = await orchestrator.generate_prompt(requirements)
        
        # Save the results
        orchestrator.save_results("prompt_generation_results.json", result)
        
        # Print the final prompt and score
        print("\n" + "="*50)
        print(f"🎯 Final Score: {result['final_score']}/1000")
        print("\n📝 Final Prompt:")
        print("-"*50)
        print(result['final_prompt'])
        print("-"*50)
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
