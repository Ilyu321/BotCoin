import time
import json
import hashlib
from typing import Any, Optional, List
from dataclasses import dataclass, asdict
import os
import shutil
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Einzelner Cache-Eintrag mit Metadaten"""
    data: Any
    timestamp: float
    ttl: int
    depends_on: List[str]  # Cache keys this entry depends on
    access_count: int = 0
    last_access: float = 0.0


class IntelligentCache:
    """Intelligenter Cache mit TTL und Dependency Management.
    
    Verwaltet Cache-Einträge mit Time-to-Live, Abhängigkeiten und
    automatischer Speicherbereinigung.
    """

    def __init__(self, cache_dir: str = "/tmp_docker/cache"):
        """Initialisiert den IntelligentCache.
        
        Args:
            cache_dir (str): Verzeichnis für Cache-Dateien
        """
        self.cache_dir = cache_dir
        self._entries = {}
        self._load_all()
        self._memory_limit_mb = 100  # Default memory limit
        self._adaptive_ttl = True
        self._memory_pressure_threshold = 80  # Memory usage percentage
        self._last_memory_check = 0

    def _load_all(self):
        """Load all cache entries from disk"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
            return

        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.json'):
                key = filename[:-5]
                try:
                    with open(os.path.join(self.cache_dir, filename), 'r') as f:
                        data = json.load(f)
                        self._entries[key] = CacheEntry(**data)
                except Exception as e:
                    logger.warning(f"Failed to load cache entry {key}: {e}")
                    continue

    def _save_entry(self, key: str, entry: CacheEntry):
        """Save cache entry to disk"""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(os.path.join(self.cache_dir, f"{key}.json"), 'w') as f:
                json.dump(asdict(entry), f)
        except Exception as e:
            logger.error(f"Failed to save cache entry {key}: {e}")

    def get(self, key: str, default=None) -> Optional[Any]:
        """Get cached data with TTL and dependency check"""
        if key not in self._entries:
            return default

        entry = self._entries[key]

        # Check TTL
        if time.time() - entry.timestamp > entry.ttl:
            logger.debug(f"Cache entry {key} expired (TTL: {entry.ttl}s)")
            self.invalidate(key)
            return default

        # Check dependencies
        for dep in entry.depends_on:
            if dep not in self._entries:
                logger.debug(f"Cache entry {key} invalidated (dependency {dep} missing)")
                self.invalidate(key)
                return default

        # Update access metrics
        entry.access_count += 1
        entry.last_access = time.time()

        # Adaptive TTL adjustment based on access frequency
        if self._adaptive_ttl and entry.access_count > 5:
            self._adjust_ttl_automatically(key)

        return entry.data

    def set(self, key: str, data: Any, ttl: int = 300, depends_on: List[str] = None):
        """Set cache entry with TTL and dependencies"""
        if depends_on is None:
            depends_on = []

        entry = CacheEntry(
            data=data,
            timestamp=time.time(),
            ttl=ttl,
            depends_on=depends_on,
            access_count=0,
            last_access=time.time()
        )
        self._entries[key] = entry
        self._save_entry(key, entry)

        # Check memory pressure after adding new entry
        self._check_memory_pressure()

    def invalidate(self, key: str):
        """Invalidate cache entry and all dependents"""
        if key in self._entries:
            del self._entries[key]
            try:
                os.remove(os.path.join(self.cache_dir, f"{key}.json"))
            except OSError:
                pass

        # Invalidate dependents (recursive)
        for other_key, entry in list(self._entries.items()):
            if key in entry.depends_on:
                self.invalidate(other_key)

    def clear(self):
        """Clear entire cache"""
        self._entries.clear()
        if os.path.exists(self.cache_dir):
            try:
                shutil.rmtree(self.cache_dir)
            except OSError as e:
                logger.error(f"Failed to clear cache directory: {e}")

    def get_stats(self) -> dict:
        """Get cache statistics"""
        total_size = 0
        for entry in self._entries.values():
            try:
                total_size += len(json.dumps(entry.data))
            except:
                pass

        return {
            'entries': len(self._entries),
            'total_size_bytes': total_size,
            'cache_dir': self.cache_dir,
            'memory_usage_mb': self._get_memory_usage()
        }

    def _get_memory_usage(self) -> float:
        """Get current memory usage of cache in MB"""
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)

    def _check_memory_pressure(self):
        """Check if memory pressure requires cache cleanup"""
        current_time = time.time()
        if current_time - self._last_memory_check < 60:
            return  # Check only once per minute

        self._last_memory_check = current_time
        memory_usage = self._get_memory_usage()
        memory_percent = psutil.virtual_memory().percent

        if memory_percent > self._memory_pressure_threshold:
            logger.warning(f"High memory pressure detected: {memory_percent}%. Cleaning up cache...")
            self._cleanup_least_used_entries()

    def _cleanup_least_used_entries(self, target_free_mb: int = 50):
        """Clean up least used cache entries to free memory"""
        if not self._entries:
            return

        # Sort entries by last access time (oldest first)
        sorted_entries = sorted(
            self._entries.items(),
            key=lambda item: item[1].last_access or 0
        )

        freed_mb = 0
        for key, entry in sorted_entries:
            if freed_mb >= target_free_mb:
                break
            
            freed_mb += self._estimate_entry_size(entry)
            self.invalidate(key)

        logger.info(f"Freed {freed_mb:.1f} MB by cleaning up least used cache entries")

    def _estimate_entry_size(self, entry: CacheEntry) -> float:
        """Estimate size of cache entry in MB"""
        try:
            data_size = len(json.dumps(entry.data))
            return data_size / (1024 * 1024)
        except:
            return 1.0  # Default estimate

    def _adjust_ttl_automatically(self, key: str):
        """Automatically adjust TTL based on access patterns"""
        entry = self._entries[key]
        
        # Increase TTL for frequently accessed entries
        if entry.access_count > 10:
            new_ttl = min(entry.ttl * 2, 3600)  # Double TTL, max 1 hour
            entry.ttl = new_ttl
            self._save_entry(key, entry)
            logger.debug(f"Increased TTL for {key} to {new_ttl}s due to frequent access")
        
        # Decrease TTL for rarely accessed entries
        elif entry.access_count < 3 and entry.ttl > 60:
            new_ttl = max(entry.ttl // 2, 60)  # Halve TTL, min 1 minute
            entry.ttl = new_ttl
            self._save_entry(key, entry)
            logger.debug(f"Decreased TTL for {key} to {new_ttl}s due to infrequent access")

    def set_memory_limit(self, limit_mb: int):
        """Set memory limit for cache"""
        self._memory_limit_mb = limit_mb
        logger.info(f"Cache memory limit set to {limit_mb} MB")

    def enable_adaptive_ttl(self, enable: bool = True):
        """Enable or disable adaptive TTL"""
        self._adaptive_ttl = enable
        logger.info(f"Adaptive TTL {'enabled' if enable else 'disabled'}")

    def get_memory_pressure_threshold(self) -> int:
        """Get current memory pressure threshold"""
        return self._memory_pressure_threshold

    def set_memory_pressure_threshold(self, threshold: int):
        """Set memory pressure threshold (percentage)"""
        self._memory_pressure_threshold = threshold
        logger.info(f"Memory pressure threshold set to {threshold}%")
# ANALYSIS_END_HOUR=22
# AI_MODEL_ANALYSIS=claude-haiku-*
# ALLOWED_TELEGRAM_USER_ID=123456789
# ANALYSIS_START_HOUR=8
# ANALYSIS_END_HOUR=22
