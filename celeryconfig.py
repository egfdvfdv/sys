"""Configuration for Celery task queue with Redis as broker and result backend."""
import os
from datetime import timedelta
from kombu import Exchange, Queue
from config import settings

# Load environment variables
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_DB = os.getenv('REDIS_DB', '0')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

# Redis connection string
redis_auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
redis_url = f"redis://{redis_auth}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Broker settings
broker_url = redis_url
result_backend = f"{redis_url}/1"  # Use a different DB for results

# Serialization
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True

# Task execution settings
task_acks_late = True
task_reject_on_worker_lost = True
task_track_started = True
worker_prefetch_multiplier = 1  # Process one task at a time
worker_concurrency = 4  # Number of concurrent workers

# Task routing and queues
task_default_queue = 'default'
task_queues = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('prompt_generation', Exchange('prompt_generation'), routing_key='prompt.generation'),
    Queue('evaluation', Exchange('evaluation'), routing_key='prompt.evaluation'),
    Queue('refinement', Exchange('refinement'), routing_key='prompt.refinement'),
)

task_routes = {
    'agi_prompt_system.tasks.generate_prompt_task': {'queue': 'prompt_generation'},
    'agi_prompt_system.tasks.evaluate_prompt_task': {'queue': 'evaluation'},
    'agi_prompt_system.tasks.refine_prompt_task': {'queue': 'refinement'},
}

# Beat settings (for scheduled tasks)
beat_schedule = {
    'cleanup-old-tasks': {
        'task': 'agi_prompt_system.tasks.cleanup_old_tasks',
        'schedule': timedelta(hours=1),  # Run every hour
        'options': {'queue': 'default'},
    },
    'monitor-queue-sizes': {
        'task': 'agi_prompt_system.tasks.monitor_queue_sizes',
        'schedule': timedelta(minutes=5),  # Run every 5 minutes
        'options': {'queue': 'default'},
    },
}

# Monitoring
event_queue_ttl = 3600  # Keep events for 1 hour
event_queue_expires = 7200  # Expire events after 2 hours
worker_send_task_events = True
task_send_sent_event = True

# Error handling
task_annotations = {
    'agi_prompt_system.tasks.generate_prompt_task': {
        'max_retries': 3,
        'default_retry_delay': 60,  # 1 minute
        'retry_backoff': True,
        'retry_backoff_max': 600,  # 10 minutes
        'retry_jitter': True,
        'acks_late': True,
        'reject_on_worker_lost': True,
    },
    'agi_prompt_system.tasks.evaluate_prompt_task': {
        'max_retries': 2,
        'default_retry_delay': 30,  # 30 seconds
        'retry_backoff': True,
        'retry_backoff_max': 300,  # 5 minutes
        'retry_jitter': True,
    },
    'agi_prompt_system.tasks.refine_prompt_task': {
        'max_retries': 2,
        'default_retry_delay': 30,  # 30 seconds
        'retry_backoff': True,
        'retry_backoff_max': 300,  # 5 minutes
        'retry_jitter': True,
    },
    '*': {
        'max_retries': 3,
        'default_retry_delay': 60,  # 1 minute
        'retry_backoff': True,
        'retry_backoff_max': 600,  # 10 minutes
        'retry_jitter': True,
    }
}

# Worker settings
worker_max_tasks_per_child = 100  # Restart worker after 100 tasks to prevent memory leaks
worker_max_memory_per_child = 500000  # 500MB
worker_redirect_stdouts = True
worker_redirect_stdouts_level = 'INFO'
worker_hijack_root_logger = False

# Result backend settings
result_expires = 86400  # 24 hours
result_persistent = True
result_extended = True

# Security
security_key = 'unsecure'  # Change in production
security_cert_store = None

# Logging
worker_log_format = """
    [%(asctime)s: %(levelname)s/%(processName)s] %(task_name)s\n    %(message)s
"""
worker_task_log_format = """
    [%(asctime)s: %(levelname)s/%(processName)s] %(task_name)s\n    %(message)s\n    \
    Task was called with args: %(task_args)s kwargs: %(task_kwargs)s\n    \
    The contents of the full task definition was:%(task_definition)s
"""

# Monitoring with Flower (if enabled)
flower_port = 5555
flower_address = '0.0.0.0'
flower_basic_auth = ['admin:admin']  # Change in production

# Enable remote control commands
worker_enable_remote_control = True

# Task compression
task_compression = 'gzip'
event_serializer = 'json'

# Task time limits (in seconds)
task_soft_time_limit = settings.CELERY_TASK_SOFT_TIME_LIMIT
task_time_limit = settings.CELERY_TASK_TIME_LIMIT

# Task result settings
task_ignore_result = False
task_store_errors_even_if_ignored = True

# Task messages settings
worker_disable_rate_limits = False
worker_prefetch_multiplier = 1
worker_send_task_events = True

# Task events
worker_send_task_events = True
task_send_sent_event = True

# Task protocol
accept_content = ['json', 'pickle']
result_accept_content = ['json', 'pickle']

# Task execution pool
worker_pool = 'prefork'  # or 'gevent', 'eventlet', 'solo'
worker_pool_restarts = True

# Task result expiration
result_expires = 86400  # 24 hours

# Message routing
task_default_exchange = 'tasks'
task_default_exchange_type = 'direct'
task_default_routing_key = 'default'

# Result backend settings
result_expires = 86400  # 1 day in seconds
result_cache_max = 1000  # Max number of results to keep in cache

# Security
worker_send_task_events = True
task_send_sent_event = True
