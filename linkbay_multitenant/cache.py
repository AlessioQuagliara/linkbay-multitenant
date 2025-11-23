"""
Sistema di caching per dati tenant.
Riduce carico DB e migliora performance.
"""
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)


class TenantCache:
    """
    Cache LRU con TTL per dati tenant.
    Thread-safe per operazioni async.
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 300,
        enable_stats: bool = True
    ):
        """
        Args:
            max_size: Numero massimo di tenant in cache
            ttl_seconds: Time-to-live per entry (default 5 min)
            enable_stats: Abilita raccolta statistiche
        """
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self.enable_stats = enable_stats
        
        # Storage
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, datetime] = {}
        self._expiry_times: Dict[str, datetime] = {}
        
        # Stats
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        # Lock per thread-safety
        self._lock = asyncio.Lock()
        
        logger.info(f"TenantCache initialized: max_size={max_size}, ttl={ttl_seconds}s")
    
    async def get(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Ottiene tenant da cache.
        Ritorna None se non presente o scaduto.
        """
        async with self._lock:
            # Check esistenza
            if tenant_id not in self._cache:
                if self.enable_stats:
                    self._misses += 1
                return None
            
            # Check scadenza
            if datetime.utcnow() > self._expiry_times[tenant_id]:
                await self._remove(tenant_id)
                if self.enable_stats:
                    self._misses += 1
                return None
            
            # Hit - aggiorna access time
            self._access_times[tenant_id] = datetime.utcnow()
            if self.enable_stats:
                self._hits += 1
            
            return self._cache[tenant_id]
    
    async def set(self, tenant_id: str, tenant_data: Dict[str, Any]):
        """Inserisce o aggiorna tenant in cache"""
        async with self._lock:
            # Evict se necessario
            if len(self._cache) >= self.max_size and tenant_id not in self._cache:
                await self._evict_lru()
            
            # Insert/update
            self._cache[tenant_id] = tenant_data
            self._access_times[tenant_id] = datetime.utcnow()
            self._expiry_times[tenant_id] = datetime.utcnow() + self.ttl
            
            logger.debug(f"Cached tenant: {tenant_id}")
    
    async def delete(self, tenant_id: str):
        """Rimuove tenant dalla cache"""
        async with self._lock:
            await self._remove(tenant_id)
    
    async def clear(self):
        """Svuota completamente la cache"""
        async with self._lock:
            self._cache.clear()
            self._access_times.clear()
            self._expiry_times.clear()
            logger.info("Cache cleared")
    
    async def _remove(self, tenant_id: str):
        """Rimuove tenant (metodo interno senza lock)"""
        self._cache.pop(tenant_id, None)
        self._access_times.pop(tenant_id, None)
        self._expiry_times.pop(tenant_id, None)
    
    async def _evict_lru(self):
        """Rimuove tenant meno recentemente usato"""
        if not self._access_times:
            return
        
        # Find LRU
        lru_tenant = min(self._access_times, key=self._access_times.get)
        await self._remove(lru_tenant)
        
        if self.enable_stats:
            self._evictions += 1
        
        logger.debug(f"Evicted LRU tenant: {lru_tenant}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Statistiche cache per monitoring"""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests
        }
    
    async def cleanup_expired(self):
        """Rimuove tutte le entry scadute"""
        async with self._lock:
            now = datetime.utcnow()
            expired = [
                tid for tid, exp_time in self._expiry_times.items()
                if now > exp_time
            ]
            
            for tenant_id in expired:
                await self._remove(tenant_id)
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired entries")


class TenantCacheService:
    """
    Service wrapper per cache tenant con fallback a DB.
    Implementa pattern cache-aside.
    """
    
    def __init__(
        self,
        cache: TenantCache,
        db_getter: Callable[[str], Any]
    ):
        """
        Args:
            cache: Istanza TenantCache
            db_getter: Async function per fetch da DB
        """
        self.cache = cache
        self.db_getter = db_getter
    
    async def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Ottiene tenant con pattern cache-aside:
        1. Cerca in cache
        2. Se miss, fetch da DB
        3. Popola cache
        """
        # Try cache first
        tenant = await self.cache.get(tenant_id)
        if tenant:
            logger.debug(f"Cache hit for tenant: {tenant_id}")
            return tenant
        
        # Cache miss - fetch from DB
        logger.debug(f"Cache miss for tenant: {tenant_id}, fetching from DB")
        tenant = await self.db_getter(tenant_id)
        
        if tenant:
            # Populate cache
            await self.cache.set(tenant_id, tenant)
        
        return tenant
    
    async def invalidate_tenant(self, tenant_id: str):
        """Invalida cache per tenant (es. dopo update)"""
        await self.cache.delete(tenant_id)
        logger.info(f"Cache invalidated for tenant: {tenant_id}")
    
    async def refresh_tenant(self, tenant_id: str):
        """Ricarica tenant da DB e aggiorna cache"""
        tenant = await self.db_getter(tenant_id)
        if tenant:
            await self.cache.set(tenant_id, tenant)
            logger.info(f"Cache refreshed for tenant: {tenant_id}")


# Background task per cleanup periodico
async def cache_cleanup_task(cache: TenantCache, interval_seconds: int = 60):
    """
    Task background per cleanup cache periodico.
    Da eseguire come background task in FastAPI.
    """
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await cache.cleanup_expired()
            
            # Log stats
            stats = cache.get_stats()
            logger.info(
                f"Cache stats: {stats['size']}/{stats['max_size']} entries, "
                f"{stats['hit_rate_percent']}% hit rate"
            )
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")


# Esempio di utilizzo
"""
from linkbay_multitenant.cache import TenantCache, TenantCacheService, cache_cleanup_task

# Setup cache
cache = TenantCache(
    max_size=1000,
    ttl_seconds=300,  # 5 minuti
    enable_stats=True
)

# DB getter function
async def get_tenant_from_db(tenant_id: str):
    async with db_session() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

# Service con cache
cache_service = TenantCacheService(cache, get_tenant_from_db)

# In dependency FastAPI
async def get_tenant_cached(tenant_id: str = Depends(get_tenant_id)):
    return await cache_service.get_tenant(tenant_id)

# Route con cache
@app.get("/tenant/info")
async def tenant_info(tenant = Depends(get_tenant_cached)):
    return tenant

# Startup event per cleanup task
@app.on_event("startup")
async def startup():
    asyncio.create_task(cache_cleanup_task(cache, interval_seconds=60))

# Invalidazione dopo update
@app.put("/admin/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, data: TenantUpdate):
    # Update DB
    await db.update_tenant(tenant_id, data)
    
    # Invalida cache
    await cache_service.invalidate_tenant(tenant_id)
    
    return {"status": "updated"}

# Monitoring endpoint
@app.get("/admin/cache/stats")
async def cache_stats():
    return cache.get_stats()
"""
