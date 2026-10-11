"""Tiny cache-based rate limiter (no extra dependencies).
Counters live in Django's cache. With the default per-process cache, limits
apply per worker process, which is still enough to stop casual brute forcing.
Point ``CACHES`` at Redis/Memcached/the DB cache if you need exact global limits.
"""
import hashlib
from django.conf import settings
from django.core.cache import cache

def client_ip(request) -> str:
    """Best-effort client IP. Only trusts X-Forwarded-For when
    TRUSTED_PROXY_COUNT > 0 (i.e. you told us how many proxies sit in front)."""
    proxies = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if proxies > 0 and forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= proxies:
            return parts[-proxies]
    return request.META.get("REMOTE_ADDR", "") or "unknown"

class RateLimit:
    def __init__(self, scope: str, limit: int, window_seconds: int):
        self.scope = scope
        self.limit = limit
        self.window = window_seconds
    def _key(self, identity: str) -> str:
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        return f"ratelimit:{self.scope}:{digest}"
    def count(self, identity: str) -> int:
        return cache.get(self._key(identity), 0)
    def is_blocked(self, identity: str) -> bool:
        return self.count(identity) >= self.limit
    def hit(self, identity: str) -> int:
        """Record one event and return the new count."""
        key = self._key(identity)
        if cache.add(key, 1, self.window):
            return 1
        try:
            return cache.incr(key)
        except ValueError:  
            cache.set(key, 1, self.window)
            return 1
    def reset(self, identity: str) -> None:
        cache.delete(self._key(identity))