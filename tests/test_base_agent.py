import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock # AsyncMock is important for async methods

# Adjust import paths based on your project structure.
# Assuming 'base_agent.py' and 'config.py' are in 'agi_prompt_system' package.
from agi_prompt_system.base_agent import BaseAgent
from agi_prompt_system.config import Config # Or ApiSettings if that's the actual class name

# We need to mock AsyncOpenAI from the openai package
# The patch target will be where AsyncOpenAI is looked up by BaseAgent,
# which is 'openai.AsyncOpenAI' if BaseAgent imports it as 'from openai import AsyncOpenAI'.
# However, BaseAgent imports it from 'openai', so the patch target is 'agi_prompt_system.base_agent.AsyncOpenAI'

class TestBaseAgent(unittest.TestCase):

    def setUp(self):
        """Set up for each test case."""
        self.mock_config = MagicMock(spec=Config)
        self.mock_config.API_BASE_URL = "https://api.example.com/v1"
        self.mock_config.API_KEY = "test_api_key"
        self.mock_config.MODEL = "test-model"

    def run_async(self, coro):
        """Helper to run async functions in tests."""
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch('agi_prompt_system.base_agent.AsyncOpenAI') # Patch where it's used by BaseAgent
    def test_call_llm_uses_async_openai(self, MockAsyncOpenAI):
        """Test that call_llm uses AsyncOpenAI client and awaits the call."""
        # Configure the mock AsyncOpenAI constructor to return a mock client instance
        mock_openai_client_instance = MagicMock()
        MockAsyncOpenAI.return_value = mock_openai_client_instance

        # Make the 'chat.completions.create' an AsyncMock so it can be awaited
        # and its calls can be asserted.
        mock_create_completion = AsyncMock()
        # Define a sample response structure that the code expects
        mock_create_completion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Mocked LLM response"))],
            model="test-model-from-response",
            usage=MagicMock(total_tokens=10)
        )
        mock_openai_client_instance.chat.completions.create = mock_create_completion

        # Instantiate BaseAgent - this will use the mocked AsyncOpenAI
        agent = BaseAgent(config=self.mock_config)
        
        # Verify AsyncOpenAI was instantiated correctly by BaseAgent
        MockAsyncOpenAI.assert_called_once_with(
            base_url=self.mock_config.API_BASE_URL,
            api_key=self.mock_config.API_KEY
        )
        self.assertEqual(agent.client, mock_openai_client_instance)

        # Call the method to be tested
        test_messages = [{"role": "user", "content": "Hello"}]
        test_temperature = 0.7
        response_content = self.run_async(agent.call_llm(messages=test_messages, temperature=test_temperature))

        # Assert that chat.completions.create was called (awaited)
        mock_create_completion.assert_awaited_once()

        # Assert the arguments passed to chat.completions.create
        mock_create_completion.assert_awaited_once_with(
            model=self.mock_config.MODEL,
            messages=test_messages,
            temperature=test_temperature,
            max_tokens=2048, # As per BaseAgent's implementation
            stream=False      # As per BaseAgent's implementation
        )
        
        # Assert the response content is returned
        self.assertEqual(response_content, "Mocked LLM response")

    def test_parse_evaluation_full_text(self):
        """Test parsing a typical evaluation text."""
        agent = BaseAgent(config=self.mock_config) # Config not directly used by parse_evaluation
        evaluation_text = """
        SCORE: 850
        FEEDBACK:
        - Clarity: 8/10 - The prompt is mostly clear.
        - Relevance: 9/10 - Highly relevant to the topic.
        - Safety: 7/10 - Could be safer.
        SUGGESTIONS:
        - Add more specific constraints.
        - Consider edge cases for safety.
        """
        expected_result = {
            "score": 850,
            "feedback": {
                "Clarity": {"score": 8, "feedback": "The prompt is mostly clear."},
                "Relevance": {"score": 9, "feedback": "Highly relevant to the topic."},
                "Safety": {"score": 7, "feedback": "Could be safer."}
            },
            "suggestions": [
                "Add more specific constraints.",
                "Consider edge cases for safety."
            ]
        }
        self.assertEqual(agent.parse_evaluation(evaluation_text), expected_result)

    def test_parse_evaluation_missing_parts(self):
        """Test parsing with missing score or suggestions."""
        agent = BaseAgent(config=self.mock_config)
        
        # Missing score
        text_no_score = """
        FEEDBACK:
        - Clarity: 8/10 - Clear.
        SUGGESTIONS:
        - Suggestion 1.
        """
        expected_no_score = {
            "score": 0, # Default
            "feedback": {"Clarity": {"score": 8, "feedback": "Clear."}},
            "suggestions": ["Suggestion 1."]
        }
        self.assertEqual(agent.parse_evaluation(text_no_score), expected_no_score)

        # Missing suggestions
        text_no_suggestions = """
        SCORE: 700
        FEEDBACK:
        - Relevance: 7/10 - Relevant.
        """
        expected_no_suggestions = {
            "score": 700,
            "feedback": {"Relevance": {"score": 7, "feedback": "Relevant."}},
            "suggestions": [] # Default
        }
        self.assertEqual(agent.parse_evaluation(text_no_suggestions), expected_no_suggestions)

    def test_parse_evaluation_malformed_feedback_score(self):
        """Test parsing with malformed feedback scores."""
        agent = BaseAgent(config=self.mock_config)
        text_malformed_feedback = """
        SCORE: 750
        FEEDBACK:
        - Clarity: Bad/10 - Not a number.
        - Relevance: 9/10 - Good.
        """
        expected_malformed = {
            "score": 750,
            "feedback": {
                # "Clarity" might be missing or have score 0 depending on implementation
                # Current implementation in BaseAgent:
                # result["feedback"][category] = {"score": 0, "feedback": feedback[1].strip()}
                "Clarity": {"score": 0, "feedback": "Not a number."},
                "Relevance": {"score": 9, "feedback": "Good."}
            },
            "suggestions": []
        }
        self.assertEqual(agent.parse_evaluation(text_malformed_feedback), expected_malformed)

    def test_parse_evaluation_empty_text(self):
        """Test parsing an empty string."""
        agent = BaseAgent(config=self.mock_config)
        expected_empty = {"score": 0, "feedback": {}, "suggestions": []}
        self.assertEqual(agent.parse_evaluation(""), expected_empty)

if __name__ == '__main__':
    unittest.main()
