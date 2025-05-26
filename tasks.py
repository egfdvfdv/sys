"""Task queue management using Celery."""
from typing import Any, Dict, Optional, TypeVar, Callable, Type
from functools import wraps
import json
from datetime import timedelta
from celery.result import AsyncResult
from agi_prompt_system.tasks import app
from .cache import CacheManager

T = TypeVar('T')

def async_task(*args, **kwargs) -> Callable:
    """
    Decorator for Celery tasks with additional features.
    
    Args:
        *args: Positional arguments for Celery's task decorator
        **kwargs: Keyword arguments for Celery's task decorator
    """
    def decorator(func: Callable[..., T]) -> Callable[..., str]:
        @wraps(func)
        def wrapper(*func_args, **func_kwargs) -> str:
            # Generate a task ID
            task_id = func_kwargs.pop('task_id', None)
            
            # Apply the task asynchronously using central app
            result = app.send_task(func.__name__, args=func_args, kwargs=func_kwargs, task_id=task_id)
            
            # Return the task ID for status checking
            return result.id
            
        return wrapper
    return decorator

class TaskManager:
    """Manager for task queue operations."""
    
    def __init__(self, cache_manager: Optional[CacheManager] = None):
        """Initialize with optional cache manager."""
        self.cache = cache_manager or CacheManager()
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the status of a task.
        
        Args:
            task_id: The ID of the task to check
            
        Returns:
            Dict containing task status and result if available
        """
        # Try to get from cache first
        cached_result = self.cache.get(f"task:{task_id}")
        if cached_result:
            return cached_result
            
        # Get from Celery
        result = AsyncResult(task_id)
        
        # Prepare response
        response = {
            'task_id': task_id,
            'status': result.state,
            'ready': result.ready(),
            'successful': result.successful(),
            'failed': result.failed(),
        }
        
        if result.ready():
            if result.successful():
                response['result'] = result.result
            else:
                response['error'] = str(result.result)
                response['traceback'] = result.traceback
        
        # Cache the result for 5 minutes
        if result.ready():
            self.cache.set(f"task:{task_id}", response, ttl=300)
        
        return response
    
    def revoke_task(self, task_id: str, terminate: bool = False) -> bool:
        """
        Revoke a running task.
        
        Args:
            task_id: The ID of the task to revoke
            terminate: Whether to terminate the task if it's running
            
        Returns:
            bool: True if the task was successfully revoked
        """
        try:
            app.control.revoke(task_id, terminate=terminate)
            self.cache.delete(f"task:{task_id}")
            return True
        except Exception as e:
            print(f"Error revoking task {task_id}: {e}")
            return False

# Utility task for cleanup remains defined in agi_prompt_system.tasks
def cleanup_old_tasks() -> None:
    """Clean up old task results from the result backend."""
    # This would be implemented based on your result backend
    pass
