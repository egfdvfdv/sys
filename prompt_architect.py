"""Agent responsible for generating and refining system prompts."""
from typing import Dict, Any, Optional
import json

from .base_agent import BaseAgent
from ..config import Config

class PromptArchitect(BaseAgent):
    """Agent that generates and refines system prompts based on feedback."""
    
    def __init__(self, config: Config):
        """Initialize the PromptArchitect with configuration."""
        super().__init__(config)
        self.version = 1
    
    async def generate_initial_prompt(self, requirements: str) -> str:
        """Generate an initial system prompt based on requirements."""
        messages = [
            {"role": "system", "content": self.config.SYSTEM_PROMPT_TEMPLATE.format(
                version=self.version,
                feedback="No previous feedback available.",
                requirements=requirements
            )}
        ]
        
        response = await self.call_llm(
            messages=messages,
            temperature=self.config.GENERATION_TEMPERATURE
        )
        
        return response.strip()
    
    async def refine_prompt(
        self, 
        current_prompt: str, 
        feedback: Dict[str, Any],
        requirements: str
    ) -> str:
        """Refine the prompt based on evaluation feedback."""
        self.version += 1
        
        # Format the feedback into a readable string
        feedback_str = "\n".join([
            f"- {category}: {data['feedback']} (Score: {data['score']}/200)"
            for category, data in feedback.get('feedback', {}).items()
        ])
        
        if feedback.get('suggestions'):
            feedback_str += "\n\nSuggestions for improvement:\n" + "\n".join(
                f"- {suggestion}" for suggestion in feedback['suggestions']
            )
        
        messages = [
            {
                "role": "system",
                "content": self.config.SYSTEM_PROMPT_TEMPLATE.format(
                    version=self.version,
                    feedback=feedback_str,
                    requirements=requirements
                )
            },
            {
                "role": "user",
                "content": f"Here's the current prompt that received a score of {feedback.get('score', 0)}/1000:\n\n{current_prompt}"
            }
        ]
        
        response = await self.call_llm(
            messages=messages,
            temperature=self.config.GENERATION_TEMPERATURE
        )
        
        return response.strip()
