"""Pydantic models for the API."""
from typing import Dict, List, Optional, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl


class TaskStatus(str, Enum):
    """Status of an asynchronous task."""
    PENDING = "pending"
    STARTED = "started"
    RETRY = "retry"
    FAILURE = "failure"
    SUCCESS = "success"


class PromptRequest(BaseModel):
    """Request model for prompt generation."""
    requirements: str = Field(..., description="Requirements for the prompt generation")
    max_iterations: Optional[int] = Field(
        None,
        description="Maximum number of refinement iterations"
    )
    temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0 to 2.0)"
    )


class PromptEvaluation(BaseModel):
    """Model for prompt evaluation results."""
    score: float = Field(..., ge=0.0, le=1000.0, description="Overall score (0-1000)")
    feedback: Dict[str, str] = Field(..., description="Detailed feedback by category")
    suggestions: List[str] = Field(..., description="List of improvement suggestions")


class PromptIteration(BaseModel):
    """Model for a single iteration of prompt refinement."""
    iteration: int = Field(..., ge=1, description="Iteration number")
    prompt: str = Field(..., description="Generated prompt")
    score: float = Field(..., ge=0.0, le=1000.0, description="Evaluation score")
    timestamp: datetime = Field(..., description="When the iteration was completed")
    evaluation: PromptEvaluation = Field(..., description="Evaluation details")


class PromptResponse(BaseModel):
    """Response model for prompt generation."""
    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(..., description="Current status of the task")
    progress: float = Field(..., ge=0.0, le=1.0, description="Progress (0.0 to 1.0)")
    result: Optional[Dict[str, Any]] = Field(
        None,
        description="Final result when status is 'success'"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if status is 'failure'"
    )
    created_at: datetime = Field(..., description="When the task was created")
    updated_at: datetime = Field(..., description="When the task was last updated")


class HealthCheck(BaseModel):
    """Health check response model."""
    status: Literal["healthy", "unhealthy"] = Field(..., description="Service health status")
    version: str = Field(..., description="API version")
    uptime: float = Field(..., description="Uptime in seconds")
    redis: bool = Field(..., description="Redis connection status")
    model_status: Dict[str, str] = Field(..., description="Status of AI models")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error message")
    code: int = Field(..., description="HTTP status code")
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )


class CacheStats(BaseModel):
    """Cache statistics model."""
    hits: int = Field(..., ge=0, description="Number of cache hits")
    misses: int = Field(..., ge=0, description="Number of cache misses")
    size: int = Field(..., ge=0, description="Current cache size in bytes")
    max_size: int = Field(..., ge=0, description="Maximum cache size in bytes")
    hit_ratio: float = Field(..., ge=0.0, le=1.0, description="Cache hit ratio")


class TaskMetrics(BaseModel):
    """Task performance metrics."""
    task_id: str = Field(..., description="Task identifier")
    duration_seconds: float = Field(..., ge=0.0, description="Task duration in seconds")
    iterations: int = Field(..., ge=0, description="Number of iterations")
    final_score: float = Field(..., ge=0.0, le=1000.0, description="Final prompt score")
    cache_hits: int = Field(..., ge=0, description="Number of cache hits")
    cache_misses: int = Field(..., ge=0, description="Number of cache misses")
    created_at: datetime = Field(..., description="When the task was created")
    completed_at: Optional[datetime] = Field(
        None,
        description="When the task was completed"
    )
