import unittest
import asyncio
from unittest.mock import MagicMock, patch, mock_open, call
import json
from datetime import datetime

# Assuming the following structure and availability of modules
# Adjust paths if your project structure is different.
from agi_prompt_system.prompt_orchestrator import PromptOrchestrator
from agi_prompt_system.config import Config # Using Config, can be ApiSettings if that's the actual name
from agi_prompt_system.utils.cache import CacheManager
from agi_prompt_system.utils.tasks import TaskManager
# PromptArchitect and PromptEvaluator are dependencies of PromptOrchestrator
from agi_prompt_system.agents import PromptArchitect, PromptEvaluator


class TestPromptOrchestrator(unittest.TestCase):

    def setUp(self):
        """Set up for each test case."""
        self.mock_config = MagicMock(spec=Config)
        self.mock_config.MAX_ITERATIONS = 5
        self.mock_config.MIN_ACCEPTABLE_SCORE = 800
        self.mock_config.MODEL = "test_model" # For save_results

        self.mock_cache_manager = MagicMock(spec=CacheManager)
        self.mock_task_manager = MagicMock(spec=TaskManager)

        # Mock the constructor and methods of PromptArchitect and PromptEvaluator
        # These will be patched for the module where PromptOrchestrator imports them.
        self.architect_patcher = patch('agi_prompt_system.prompt_orchestrator.PromptArchitect')
        self.evaluator_patcher = patch('agi_prompt_system.prompt_orchestrator.PromptEvaluator')

        self.MockPromptArchitect = self.architect_patcher.start()
        self.MockPromptEvaluator = self.evaluator_patcher.start()

        # Create mock instances for architect and evaluator
        self.mock_architect_instance = self.MockPromptArchitect.return_value
        self.mock_evaluator_instance = self.MockPromptEvaluator.return_value
        
        # Instantiate PromptOrchestrator with mocked dependencies
        self.orchestrator = PromptOrchestrator(
            config=self.mock_config,
            cache_manager=self.mock_cache_manager,
            task_manager=self.mock_task_manager
        )
        
        # Ensure that the PromptOrchestrator's internal architect and evaluator
        # are the instances we created from the mocked classes.
        self.MockPromptArchitect.assert_called_once_with(self.mock_config)
        self.MockPromptEvaluator.assert_called_once_with(self.mock_config)
        self.orchestrator.architect = self.mock_architect_instance
        self.orchestrator.evaluator = self.mock_evaluator_instance


    def tearDown(self):
        """Clean up after each test case."""
        self.architect_patcher.stop()
        self.evaluator_patcher.stop()

    def run_async(self, coro):
        """Helper to run async functions in tests."""
        return asyncio.get_event_loop().run_until_complete(coro)

    # Test Cases Start Here

    async def mock_generate_initial_prompt(self, requirements):
        return f"Initial prompt for {requirements}"

    async def mock_refine_prompt(self, current_prompt, feedback, requirements):
        return f"Refined: {current_prompt}"

    async def mock_evaluate_prompt(self, prompt_text, score=700): # Allow score to be passed
        return {"score": score, "feedback": "Some feedback", "suggestions": []}

    def test_generate_prompt_statelessness(self):
        """Test that generate_prompt calls are stateless regarding iteration results."""
        # Configure mocks for PromptArchitect and PromptEvaluator/cached_evaluation
        self.mock_architect_instance.generate_initial_prompt.side_effect = self.mock_generate_initial_prompt
        self.mock_architect_instance.refine_prompt.side_effect = self.mock_refine_prompt
        
        # Mock _evaluate_prompt_cached which is used internally by generate_prompt
        # Patch it directly on the orchestrator instance for simplicity in this test
        self.orchestrator._evaluate_prompt_cached = MagicMock()
        self.orchestrator._evaluate_prompt_cached.side_effect = [
            self.mock_evaluate_prompt("Initial prompt for req1", score=700), # Call 1, Iter 1
            self.mock_evaluate_prompt("Refined: Initial prompt for req1", score=750), # Call 1, Iter 2 (stops due to max_iter=2)
            self.mock_evaluate_prompt("Initial prompt for req2", score=720), # Call 2, Iter 1
            self.mock_evaluate_prompt("Refined: Initial prompt for req2", score=780), # Call 2, Iter 2 (stops due to max_iter=2)
        ]

        self.mock_cache_manager.get.return_value = None # Ensure no cache hit for prompt_gen

        # Call 1
        result1 = self.run_async(self.orchestrator.generate_prompt(requirements="req1", max_iterations=2))
        self.assertEqual(len(result1["iterations"]), 2)
        self.assertEqual(result1["iterations"][0]["prompt"], "Initial prompt for req1")
        self.assertEqual(result1["iterations"][0]["score"], 700)
        self.assertEqual(result1["iterations"][1]["prompt"], "Refined: Initial prompt for req1")
        self.assertEqual(result1["iterations"][1]["score"], 750)

        # Reset side effect for the mock if it's stateful in a way that matters across calls
        # For this specific side_effect list, it will continue from where it left off if not reset.
        # Or, re-assign a new side_effect list if needed.
        # Here, the single list is fine as it covers both calls.

        # Call 2
        result2 = self.run_async(self.orchestrator.generate_prompt(requirements="req2", max_iterations=2))
        self.assertEqual(len(result2["iterations"]), 2)
        self.assertEqual(result2["iterations"][0]["prompt"], "Initial prompt for req2")
        self.assertEqual(result2["iterations"][0]["score"], 720)
        self.assertEqual(result2["iterations"][1]["prompt"], "Refined: Initial prompt for req2")
        self.assertEqual(result2["iterations"][1]["score"], 780)
        
        # Verify that iterations from call 1 are not in call 2
        self.assertNotEqual(result1["iterations"][0]["prompt"], result2["iterations"][0]["prompt"])


    def test_generate_prompt_progress_callback(self):
        """Test that progress_callback is called with correct data."""
        mock_progress_callback = MagicMock()
        
        self.mock_architect_instance.generate_initial_prompt.side_effect = self.mock_generate_initial_prompt
        # For this test, let the score be high enough to stop after 1 iteration.
        self.orchestrator._evaluate_prompt_cached = MagicMock(return_value=self.mock_evaluate_prompt("Initial prompt for req_progress", score=self.mock_config.MIN_ACCEPTABLE_SCORE))
        self.mock_cache_manager.get.return_value = None # No cache hit

        task_id_val = "test_task_123"
        self.run_async(self.orchestrator.generate_prompt(
            requirements="req_progress",
            max_iterations=1,
            task_id=task_id_val,
            progress_callback=mock_progress_callback
        ))

        self.assertEqual(mock_progress_callback.call_count, 2) # EVALUATING and EVALUATED

        # Check first call (EVALUATING)
        call1_args = mock_progress_callback.call_args_list[0][0][0]
        self.assertEqual(call1_args["task_id"], task_id_val)
        self.assertEqual(call1_args["iteration"], 1)
        self.assertEqual(call1_args["status"], "EVALUATING")
        self.assertIsNone(call1_args["current_score"])

        # Check second call (EVALUATED)
        call2_args = mock_progress_callback.call_args_list[1][0][0]
        self.assertEqual(call2_args["task_id"], task_id_val)
        self.assertEqual(call2_args["iteration"], 1)
        self.assertEqual(call2_args["status"], "EVALUATED")
        self.assertEqual(call2_args["current_score"], self.mock_config.MIN_ACCEPTABLE_SCORE)
        self.assertIn("details", call2_args)
        self.assertEqual(call2_args["details"]["prompt"], "Initial prompt for req_progress")

    def test_generate_prompt_max_iterations(self):
        """Test generate_prompt stops after max_iterations."""
        max_iters = 2
        self.mock_architect_instance.generate_initial_prompt.side_effect = self.mock_generate_initial_prompt
        self.mock_architect_instance.refine_prompt.side_effect = self.mock_refine_prompt
        
        # Ensure score never reaches MIN_ACCEPTABLE_SCORE to force max_iterations
        low_score = self.mock_config.MIN_ACCEPTABLE_SCORE - 100 
        self.orchestrator._evaluate_prompt_cached = MagicMock(side_effect=[
            self.mock_evaluate_prompt("Initial prompt for req_max_iter", score=low_score),
            self.mock_evaluate_prompt("Refined: Initial prompt for req_max_iter", score=low_score),
            self.mock_evaluate_prompt("Refined: Refined: Initial prompt for req_max_iter", score=low_score), # Should not be called
        ])
        self.mock_cache_manager.get.return_value = None

        result = self.run_async(self.orchestrator.generate_prompt(requirements="req_max_iter", max_iterations=max_iters))
        
        self.assertEqual(len(result["iterations"]), max_iters)
        # _evaluate_prompt_cached should be called `max_iters` times
        self.assertEqual(self.orchestrator._evaluate_prompt_cached.call_count, max_iters)


    def test_generate_prompt_target_score_achieved(self):
        """Test generate_prompt stops when target score is achieved."""
        self.mock_architect_instance.generate_initial_prompt.side_effect = self.mock_generate_initial_prompt
        
        # Mock evaluation to return a high score on the first try
        high_score = self.mock_config.MIN_ACCEPTABLE_SCORE
        self.orchestrator._evaluate_prompt_cached = MagicMock(
            return_value=self.mock_evaluate_prompt("Initial prompt for req_target_score", score=high_score)
        )
        self.mock_cache_manager.get.return_value = None

        result = self.run_async(self.orchestrator.generate_prompt(requirements="req_target_score", max_iterations=5))
        
        self.assertEqual(len(result["iterations"]), 1) # Should stop after 1 iteration
        self.assertEqual(result["final_score"], high_score)
        self.orchestrator._evaluate_prompt_cached.assert_called_once()


    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_results(self, mock_json_dump, mock_file_open):
        """Test save_results writes correct data structure to file."""
        filepath = "test_results.json"
        generation_output = {
            "task_id": "task123",
            "final_prompt": "Final awesome prompt",
            "final_score": 950,
            "iterations": [
                {"iteration": 1, "prompt": "Prompt v1", "score": 700, "feedback": {}, "timestamp": "ts1"},
                {"iteration": 2, "prompt": "Prompt v2", "score": 950, "feedback": {}, "timestamp": "ts2"}
            ],
            "requirements": "Some requirements",
            "completed_at": "ts_completed"
        }

        # Mock orchestrator's config as it's used in save_results
        self.orchestrator.config.MODEL = "test_model_from_orchestrator_config"
        self.orchestrator.config.MIN_ACCEPTABLE_SCORE = 850 # Different from setUp to ensure this is used
        self.orchestrator.config.MAX_ITERATIONS = 10

        self.orchestrator.save_results(filepath, generation_output)

        mock_file_open.assert_called_once_with(filepath, 'w', encoding='utf-8')
        
        # Check what was passed to json.dump
        # The first argument to json.dump is the data, the second is the file handle
        args, kwargs = mock_json_dump.call_args
        dumped_data = args[0]
        
        self.assertEqual(dumped_data["results"], generation_output["iterations"])
        self.assertEqual(dumped_data["config"]["model"], "test_model_from_orchestrator_config")
        self.assertEqual(dumped_data["config"]["min_acceptable_score"], 850)
        self.assertEqual(dumped_data["config"]["max_iterations"], 10)
        self.assertIn("timestamp", dumped_data) # save_results adds its own timestamp

if __name__ == '__main__':
    unittest.main()
