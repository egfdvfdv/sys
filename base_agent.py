"""Base class for all agents in the AGI Prompt System."""
from typing import Dict, Any, Optional, List
import json
from openai import AsyncOpenAI

from ..config import Config

class BaseAgent:
    """Base class for all agents with common functionality."""
    
    def __init__(self, config: Config):
        """Initialize the agent with configuration."""
        self.config = config
        self.client = AsyncOpenAI(
            base_url=self.config.API_BASE_URL,
            api_key=self.config.API_KEY
        )
    
    async def call_llm(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """Make an API call to the LLM using the OpenAI client."""
        try:
            print("\n" + "="*50)
            print(f"Calling LLM API at: {self.config.API_BASE_URL}")
            print(f"Using model: {self.config.MODEL}")
            print("Request payload:")
            print(json.dumps({
                "model": self.config.MODEL,
                "messages": messages,
                "temperature": temperature
            }, indent=2))
            
            response = await self.client.chat.completions.create(
                model=self.config.MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=2048,
                stream=False
            )
            
            print("\nResponse received:")
            print(f"Model: {response.model}")
            print(f"Usage: {response.usage}")
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"\nError calling LLM: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response content: {e.response.text}")
            raise
    
    def parse_evaluation(self, evaluation_text: str) -> Dict[str, Any]:
        """Parse the evaluation text into a structured format."""
        result = {"score": 0, "feedback": {}, "suggestions": []}
        
        # Extract score
        score_line = next((line for line in evaluation_text.split('\n') 
                         if line.strip().startswith('SCORE:')), None)
        if score_line:
            try:
                result["score"] = int(score_line.split(':')[1].strip())
            except (IndexError, ValueError):
                pass
        
        # Extract feedback categories
        feedback_section = False
        for line in evaluation_text.split('\n'):
            line = line.strip()
            if line.startswith('FEEDBACK:'):
                feedback_section = True
                continue
            if line.startswith('SUGGESTIONS:'):
                feedback_section = False
                continue
                
            if feedback_section and line.startswith('-'):
                parts = line[1:].split(':', 1)
                if len(parts) == 2:
                    category = parts[0].strip()
                    feedback = parts[1].split('-', 1)
                    if len(feedback) == 2:
                        score_part = feedback[0].strip()
                        try:
                            score = int(score_part)
                            result["feedback"][category] = {
                                "score": score,
                                "feedback": feedback[1].strip()
                            }
                        except ValueError:
                            result["feedback"][category] = {
                                "score": 0,
                                "feedback": feedback[1].strip()
                            }
            
            elif line.startswith('- '):
                result["suggestions"].append(line[2:].strip())
        
        return result
