"""Service for Redis caching."""

import json
import logging
from typing import Any, Optional
from redis import Redis
from app.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Redis cache service for storing frequently accessed data."""
    
    def __init__(self):
        """Initialize Redis connection."""
        try:
            self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
            self.redis.ping()
            logger.info("Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis cache connection failed: {e}. Caching disabled.")
            self.redis = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.redis:
            return None
        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL (default 5 minutes)."""
        if not self.redis:
            return False
        try:
            self.redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self.redis:
            return False
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if not self.redis:
            return 0
        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
        except Exception as e:
            logger.warning(f"Cache clear error for pattern {pattern}: {e}")
        return 0


# Global cache instance
cache = CacheService()


# Cache key builders
def make_user_key(user_id: str) -> str:
    """Build cache key for user."""
    return f"user:{user_id}"


def make_contact_key(contact_id: str) -> str:
    """Build cache key for contact."""
    return f"contact:{contact_id}"


def make_campaign_key(campaign_id: str) -> str:
    """Build cache key for campaign."""
    return f"campaign:{campaign_id}"


def make_search_key(query: str, offset: int, limit: int) -> str:
    """Build cache key for search results."""
    return f"search:{query}:{offset}:{limit}"


def invalidate_user_cache(user_id: str):
    """Invalidate user cache."""
    cache.delete(make_user_key(user_id))


def invalidate_contact_cache(contact_id: str):
    """Invalidate contact cache."""
    cache.delete(make_contact_key(contact_id))


def invalidate_campaign_cache(campaign_id: str):
    """Invalidate campaign cache."""
    cache.delete(make_campaign_key(campaign_id))


def invalidate_search_cache():
    """Invalidate all search caches."""
    cache.clear_pattern("search:*")
