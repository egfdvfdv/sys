"""Agent responsible for evaluating the quality of system prompts."""
from typing import Dict, Any, Optional

from .base_agent import BaseAgent
from ..config import Config

class PromptEvaluator(BaseAgent):
    """Agent that evaluates the quality of system prompts and provides feedback."""
    
    def __init__(self, config: Config):
        """Initialize the PromptEvaluator with configuration."""
        super().__init__(config)
    
    async def evaluate_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Evaluate a system prompt and provide a score with detailed feedback.
        
        Args:
            prompt: The system prompt to evaluate
            
        Returns:
            Dict containing the score, feedback, and suggestions
        """
        messages = [
            {
                "role": "system",
                "content": self.config.EVALUATION_PROMPT.format(prompt=prompt)
            },
            {
                "role": "user",
                "content": "Please evaluate this system prompt and provide your score and feedback."
            }
        ]
        
        evaluation_text = await self.call_llm(
            messages=messages,
            temperature=self.config.EVALUATION_TEMPERATURE
        )
        
        # Parse the evaluation into a structured format
        evaluation = self.parse_evaluation(evaluation_text)
        
        # Ensure the score is within 0-1000 range
        evaluation["score"] = max(0, min(1000, evaluation.get("score", 0)))
        
        return evaluation
