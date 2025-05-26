"""Main FastAPI application for the AGI Prompt System API."""
import time
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.prometheus import PrometheusMetricsExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.metrics import get_meter_provider, set_meter_provider
from prometheus_client import start_http_server as start_metrics_server

from . import __version__
from .models import (
    PromptRequest,
    PromptResponse,
    HealthCheck,
    ErrorResponse,
    CacheStats,
    TaskMetrics
)
from ..config import Config
from ..prompt_orchestrator import PromptOrchestrator
from ..utils.cache import CacheManager
from agi_prompt_system.tasks import generate_prompt_task

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize configuration and components
config = Config()
orchestrator = PromptOrchestrator(config)
cache = CacheManager()

# Application metadata
APP_NAME = "agi-prompt-system"
APP_VERSION = __version__
START_TIME = time.time()

# Initialize OpenTelemetry
def setup_telemetry():
    """Set up OpenTelemetry tracing and metrics."""
    resource = Resource(attributes={
        "service.name": APP_NAME,
        "service.version": APP_VERSION
    })
    
    # Set up tracing
    trace.set_tracer_provider(TracerProvider(resource=resource))
    
    # Set up metrics
    metrics_exporter = PrometheusMetricsExporter()
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metrics_exporter]
    )
    set_meter_provider(meter_provider)
    
    # Start Prometheus metrics server
    start_metrics_server(port=8001)
    
    return get_meter_provider()

# Initialize metrics
meter = setup_telemetry()

# Create metrics
request_counter = meter.create_counter(
    "api_requests_total",
    description="Total number of API requests"
)

request_duration = meter.create_histogram(
    "api_request_duration_seconds",
    description="API request duration in seconds"
)

# Create FastAPI app
app = FastAPI(
    title="AGI Prompt System API",
    description="API for generating and refining AGI system prompts",
    version=APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Middleware to measure request processing time."""
    start_time = time.time()
    
    # Increment request counter
    request_counter.add(1, {"method": request.method, "endpoint": request.url.path})
    
    # Process request
    response = await call_next(request)
    
    # Record duration
    process_time = time.time() - start_time
    request_duration.record(process_time, {
        "method": request.method,
        "endpoint": request.url.path,
        "status_code": response.status_code
    })
    
    # Add headers
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            code=exc.status_code,
            details={"path": request.url.path}
        ).dict()
    )

# Health check endpoint
@app.get(
    "/api/health",
    response_model=HealthCheck,
    tags=["Monitoring"]
)
async def health_check():
    """Health check endpoint."""
    # Check Redis connection
    redis_ok = False
    try:
        redis_ok = cache.ping()
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
    
    return HealthCheck(
        status="healthy" if redis_ok else "unhealthy",
        version=APP_VERSION,
        uptime=time.time() - START_TIME,
        redis=redis_ok,
        model_status={"nvidia/llama-3.1-nemotron-ultra-253b-v1": "available"}
    )

# Cache endpoints
@app.get(
    "/api/cache/stats",
    response_model=CacheStats,
    tags=["Cache"]
)
async def get_cache_stats():
    """Get cache statistics."""
    stats = cache.get_stats()
    return CacheStats(
        hits=stats.get("hits", 0),
        misses=stats.get("misses", 0),
        size=stats.get("bytes", 0),
        max_size=stats.get("max_memory", 0),
        hit_ratio=stats.get("hit_ratio", 0.0)
    )

@app.post(
    "/api/cache/clear",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Cache"]
)
async def clear_cache():
    """Clear all cached data."""
    cache.clear_all()
    return None

# Prompt generation endpoints
@app.post(
    "/api/prompts/generate",
    response_model=PromptResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Prompts"]
)
async def generate_prompt(request: PromptRequest):
    """Submit a prompt generation request via Celery."""
    try:
        async_result = generate_prompt_task.delay(request.task_id if hasattr(request, 'task_id') else None, request.dict())
        return PromptResponse(
            task_id=async_result.id,
            status=TaskStatus.PENDING,
            progress=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/api/prompts/tasks/{task_id}",
    response_model=PromptResponse,
    tags=["Prompts"]
)
async def get_task_status(task_id: str) -> PromptResponse:
    """Get the status of a prompt generation task."""
    task_info = orchestrator.get_task_status(task_id)
    if not task_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    return PromptResponse(**task_info)

# Metrics endpoint
@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    # This is handled by the Prometheus client library
    pass

# Frontend route
@app.get("/", include_in_schema=False)
async def serve_frontend(request: Request):
    """Serve the frontend application."""
    return templates.TemplateResponse("index.html", {"request": request})

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "agi_prompt_system.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
