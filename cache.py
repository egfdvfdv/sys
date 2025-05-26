"""
Redis-based caching utilities for the AGI Prompt System.

This module provides a high-level interface for caching data in Redis with support for:
- Key-value storage with TTL
- Cache invalidation
- Statistics tracking
- Namespacing
"""
import json
import logging
from typing import Any, Optional, Dict, TypeVar, Type, Callable, Union
from functools import wraps
import pickle
import hashlib
from datetime import timedelta
import redis
from redis.exceptions import RedisError

from .config import settings

logger = logging.getLogger(__name__)

# Type variable for generic return type
T = TypeVar('T')

class CacheManager:
    """Manager for Redis-based caching operations."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize the cache manager.
        
        Args:
            redis_client: Optional Redis client instance. If not provided, a new one will be created.
        """
        self.redis = redis_client or self._create_redis_client()
        self._key_prefix = f"{settings.CACHE_PREFIX}:" if hasattr(settings, 'CACHE_PREFIX') else "agi_prompt:"
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }
    
    def _create_redis_client(self) -> redis.Redis:
        """Create a Redis client using application settings."""
        try:
            return redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if hasattr(settings, 'REDIS_PASSWORD') else None,
                decode_responses=False,  # We'll handle encoding/decoding ourselves
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
        except Exception as e:
            logger.error(f"Failed to create Redis client: {e}")
            raise
    
    def _make_key(self, key: str) -> str:
        """Create a namespaced cache key.
        
        Args:
            key: The base key to namespace.
            
        Returns:
            str: A namespaced key.
        """
        return f"{self._key_prefix}{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize a value for storage in Redis.
        
        Args:
            value: The value to serialize.
            
        Returns:
            bytes: The serialized value.
        """
        try:
            return json.dumps(value).encode('utf-8')
        except TypeError as e:
            logger.error(f"Failed to serialize value to JSON: {e}")
            raise ValueError(f"Could not serialize value to JSON: {e}")
    
    def _deserialize(self, value: bytes) -> Any:
        """Deserialize a value from Redis.
        
        Args:
            value: The serialized value from Redis.
            
        Returns:
            Any: The deserialized value.
        """
        if value is None:
            return None
        try:
            return json.loads(value.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to deserialize JSON value: {e}")
            return None
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the cache.
        
        Args:
            key: The key to retrieve.
            default: The default value to return if the key is not found.
            
        Returns:
            The cached value or the default if not found.
        """
        try:
            value = self.redis.get(self._make_key(key))
            if value is not None:
                self.stats['hits'] += 1
                return self._deserialize(value)
            self.stats['misses'] += 1
            return default
        except RedisError as e:
            self.stats['errors'] += 1
            logger.error(f"Redis error getting key {key}: {e}")
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the cache.
        
        Args:
            key: The key to set.
            value: The value to cache.
            ttl: Time to live in seconds. If None, uses the default TTL.
            
        Returns:
            bool: True if the operation was successful.
        """
        if ttl is None:
            ttl = settings.CACHE_TTL if hasattr(settings, 'CACHE_TTL') else 86400
            
        try:
            serialized = self._serialize(value)
            if ttl > 0:
                result = self.redis.setex(
                    name=self._make_key(key),
                    time=ttl,
                    value=serialized
                )
            else:
                result = self.redis.set(
                    name=self._make_key(key),
                    value=serialized
                )
            self.stats['sets'] += 1
            return bool(result)
        except RedisError as e:
            self.stats['errors'] += 1
            logger.error(f"Redis error setting key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a key from the cache.
        
        Args:
            key: The key to delete.
            
        Returns:
            bool: True if the key was deleted, False otherwise.
        """
        try:
            result = self.redis.delete(self._make_key(key))
            self.stats['deletes'] += 1
            return bool(result > 0)
        except RedisError as e:
            self.stats['errors'] += 1
            logger.error(f"Redis error deleting key {key}: {e}")
            return False
    
    def clear(self, pattern: str = '*') -> int:
        """Clear keys matching a pattern from the cache.
        
        Args:
            pattern: The pattern to match keys against.
            
        Returns:
            int: The number of keys deleted.
        """
        try:
            keys = self.redis.keys(self._make_key(pattern))
            if not keys:
                return 0
                
            # Delete in batches to avoid blocking Redis for too long
            batch_size = 1000
            deleted = 0
            
            for i in range(0, len(keys), batch_size):
                batch = keys[i:i + batch_size]
                deleted += self.redis.delete(*batch)
                
            self.stats['deletes'] += deleted
            return deleted
        except RedisError as e:
            self.stats['errors'] += 1
            logger.error(f"Redis error clearing cache with pattern {pattern}: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dict[str, int]: A dictionary of cache statistics.
        """
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }
    
    def get_ttl(self, key: str) -> Optional[int]:
        """Get the TTL for a key.
        
        Args:
            key: The key to check.
            
        Returns:
            Optional[int]: The TTL in seconds, or None if the key does not exist or has no TTL.
        """
        try:
            ttl = self.redis.ttl(self._make_key(key))
            return ttl if ttl >= 0 else None
        except RedisError as e:
            self.stats['errors'] += 1
            logger.error(f"Redis error getting TTL for key {key}: {e}")
            return None
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.
        
        Args:
            key: The key to check.
            
        Returns:
            bool: True if the key exists, False otherwise.
        """
        try:
            return bool(self.redis.exists(self._make_key(key)))
        except RedisError as e:
            self.stats['errors'] += 1
            logger.error(f"Redis error checking existence of key {key}: {e}")
            return False
    
    def cache_result(
        self, 
        ttl: Optional[int] = None, 
        key_func: Optional[Callable[..., str]] = None,
        unless: Optional[Callable[..., bool]] = None
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator to cache the result of a function.
        
        Args:
            ttl: Time to live in seconds for the cached result.
            key_func: Function to generate a cache key from function arguments.
                     If None, a default key will be generated.
            unless: Callable that returns True if the result should not be cached.
                   Useful for skipping cache on certain conditions.
                   
        Returns:
            A decorator that caches the result of the decorated function.
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> T:
                # Skip caching if unless condition is met
                if unless and unless(*args, **kwargs):
                    return func(*args, **kwargs)
                
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    func_name = func.__module__ + '.' + func.__qualname__
                    key_parts = [func_name] + [str(arg) for arg in args] + [f"{k}={v}" for k, v in kwargs.items()]
                    key_str = ':'.join(key_parts)
                    cache_key = hashlib.md5(key_str.encode('utf-8')).hexdigest()
                
                # Try to get from cache
                cached = self.get(cache_key)
                if cached is not None:
                    return cached
                
                # Call the function and cache the result
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl=ttl)
                return result
            
            return wrapper
        return decorator

# Global cache instance
cache = CacheManager()

def get_cache() -> CacheManager:
    """Get the global cache instance."""
    return cache
