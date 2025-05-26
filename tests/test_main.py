import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import FastAPI # For type hinting if needed, not strictly for app import

# Adjust import paths based on your project structure.
# Assuming 'main.py' is in 'agi_prompt_system.api' and can be imported as such.
# The 'app' instance needs to be imported from where it's defined.
from agi_prompt_system.api.main import app

# Import dependency provider functions and the classes they provide, for overriding.
# These paths also depend on your project structure.
from agi_prompt_system.api.main import get_cache_manager, get_prompt_orchestrator, get_settings, get_task_manager
from agi_prompt_system.utils.cache import CacheManager
from agi_prompt_system.prompt_orchestrator import PromptOrchestrator
from agi_prompt_system.config import ApiSettings # Or Config, if that's the actual name
from agi_prompt_system.utils.tasks import TaskManager


class TestMainAPI(unittest.TestCase):

    def setUp(self):
        """Set up for each test case."""
        self.client = TestClient(app)

    def tearDown(self):
        """Clean up after each test, especially dependency_overrides."""
        app.dependency_overrides = {}

    def test_csp_header_set_correctly(self):
        """Test that the Content-Security-Policy header is set correctly."""
        response = self.client.get("/api/health") # Any endpoint that applies middleware
        
        self.assertIn("Content-Security-Policy", response.headers)
        csp_header = response.headers["Content-Security-Policy"]
        
        # Verify absence of 'unsafe-inline' for script-src and style-src
        self.assertNotIn("'unsafe-inline'", csp_header.split("script-src")[1].split(";")[0])
        self.assertNotIn("'unsafe-inline'", csp_header.split("style-src")[1].split(";")[0])
        
        # Verify presence of 'self' and cdn.jsdelivr.net for script-src
        script_src_policy = csp_header.split("script-src")[1].split(";")[0]
        self.assertIn("'self'", script_src_policy)
        self.assertIn("cdn.jsdelivr.net", script_src_policy)
        
        # Verify presence of 'self' and cdn.jsdelivr.net for style-src
        style_src_policy = csp_header.split("style-src")[1].split(";")[0]
        self.assertIn("'self'", style_src_policy)
        self.assertIn("cdn.jsdelivr.net", style_src_policy)

    def test_dependency_injection_for_health_endpoint(self):
        """Test dependency injection for the /api/health endpoint (CacheManager)."""
        mock_cache_manager_instance = MagicMock(spec=CacheManager)
        # Simulate the ping method, assuming it's called by the health check
        mock_cache_manager_instance.ping = MagicMock(return_value=True) 
        # If health_check uses cache.redis.ping():
        mock_cache_manager_instance.redis = MagicMock()
        mock_cache_manager_instance.redis.ping = MagicMock(return_value=True)


        def mock_get_cache_manager() -> CacheManager:
            return mock_cache_manager_instance

        app.dependency_overrides[get_cache_manager] = mock_get_cache_manager

        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        
        # Check if the mock CacheManager's relevant method was called.
        # Based on main.py's health_check, it tries:
        # 1. cache.ping()
        # 2. cache.redis.ping() if cache.ping doesn't exist
        if hasattr(mock_cache_manager_instance, 'ping'):
             mock_cache_manager_instance.ping.assert_called_once()
        else:
            mock_cache_manager_instance.redis.ping.assert_called_once()


    def test_dependency_injection_for_task_status_endpoint(self):
        """Test dependency injection for /api/prompts/tasks/{task_id} (PromptOrchestrator)."""
        mock_orchestrator_instance = MagicMock(spec=PromptOrchestrator)
        mock_task_info = {
            "task_id": "test_task_123",
            "status": "SUCCESS", # Using string status as per PromptResponse model likely
            "progress": 100.0,
            "result": {"final_prompt": "Test"},
            "created_at": "2023-01-01T10:00:00Z", # needs to be datetime compatible or str
            "updated_at": "2023-01-01T10:01:00Z",
            # Add other fields if PromptResponse expects them, or ensure mock_task_info matches
            # what orchestrator.get_task_status returns and what PromptResponse can handle.
            # For example, if PromptResponse expects datetime objects:
            # from datetime import datetime
            # "created_at": datetime.utcnow(),
            # "updated_at": datetime.utcnow(),
        }
        mock_orchestrator_instance.get_task_status = MagicMock(return_value=mock_task_info)

        # Mock providers for PromptOrchestrator's dependencies
        # These can return fresh MagicMocks if their direct interaction isn't tested here.
        mock_settings_instance = MagicMock(spec=ApiSettings)
        mock_cache_instance_for_orchestrator = MagicMock(spec=CacheManager)
        mock_task_manager_instance = MagicMock(spec=TaskManager)

        def mock_get_settings_override():
            return mock_settings_instance
        
        def mock_get_cache_manager_for_orchestrator():
            return mock_cache_instance_for_orchestrator

        def mock_get_task_manager_override():
            return mock_task_manager_instance

        def mock_get_prompt_orchestrator_override() -> PromptOrchestrator:
            return mock_orchestrator_instance

        # Override all dependencies for get_prompt_orchestrator
        # Or, if get_prompt_orchestrator correctly uses Depends for its own args,
        # we might only need to override the top-level one.
        # For robustness, override all that get_prompt_orchestrator depends on,
        # or ensure get_prompt_orchestrator itself is simple enough.
        # From previous task, get_prompt_orchestrator takes (settings, cache, tm).
        
        app.dependency_overrides[get_settings] = mock_get_settings_override
        # Note: get_cache_manager is already used by health check.
        # If we want a *different* mock cache manager for the orchestrator, we need care.
        # But here, get_prompt_orchestrator depends on get_cache_manager, so it will get
        # whatever get_cache_manager is providing at the time.
        # Let's assume we're fine with it getting a generic CacheManager mock for this test
        # or the one from the health check test if tests run in a specific order without cleanup (bad idea).
        # tearDown should clear overrides, so this should be fine.
        app.dependency_overrides[get_cache_manager] = mock_get_cache_manager_for_orchestrator
        app.dependency_overrides[get_task_manager] = mock_get_task_manager_override
        app.dependency_overrides[get_prompt_orchestrator] = mock_get_prompt_orchestrator_override
        
        task_id = "test_task_123"
        # Need to ensure PromptResponse can be initialized from mock_task_info.
        # If PromptResponse expects datetime objects, mock_task_info needs them.
        # For now, assuming string dates are handled or model validation allows them.
        # Let's adjust mock_task_info to be more robust for Pydantic model.
        from agi_prompt_system.models import TaskStatus # Assuming this exists
        from datetime import datetime
        mock_task_info_for_response = {
            "task_id": task_id,
            "status": TaskStatus.SUCCESS, # Use the enum if possible
            "progress": 1.0, # Pydantic might convert 100.0 to 1.0 if it's a float from 0-1
            "result": {"final_prompt": "Test"},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            # These might be optional or have defaults in PromptResponse
            "final_prompt_text": None, 
            "evaluation_results": None,
            "error_message": None,
        }
        mock_orchestrator_instance.get_task_status.return_value = mock_task_info_for_response


        response = self.client.get(f"/api/prompts/tasks/{task_id}")
        
        self.assertEqual(response.status_code, 200)
        mock_orchestrator_instance.get_task_status.assert_called_once_with(task_id)
        
        # Check if the response data matches (some key fields)
        response_data = response.json()
        self.assertEqual(response_data["task_id"], task_id)
        self.assertEqual(response_data["status"], "SUCCESS") # Enum would be stringified by FastAPI


if __name__ == '__main__':
    unittest.main()
