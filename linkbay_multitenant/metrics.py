"""
Sistema di metriche e monitoring per multitenant.
Traccia performance, utilizzo risorse, e attività per tenant.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import logging

logger = logging.getLogger(__name__)


class TenantMetrics:
    """
    Raccoglie e gestisce metriche per singolo tenant.
    """
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.created_at = datetime.utcnow()
        
        # Contatori
        self.total_requests = 0
        self.failed_requests = 0
        self.total_response_time_ms = 0.0
        
        # Storage & users
        self.storage_used_bytes = 0
        self.active_users = 0
        self.total_users = 0
        
        # Rate limiting
        self.requests_per_minute: List[int] = []
        self.last_minute_requests = 0
        
        # DB queries
        self.total_queries = 0
        self.slow_queries = 0
    
    def record_request(self, response_time_ms: float, success: bool = True):
        """Registra una richiesta HTTP"""
        self.total_requests += 1
        self.total_response_time_ms += response_time_ms
        
        if not success:
            self.failed_requests += 1
        
        # Rate tracking
        self.last_minute_requests += 1
    
    def record_query(self, query_time_ms: float, slow_threshold_ms: float = 1000):
        """Registra una query DB"""
        self.total_queries += 1
        
        if query_time_ms > slow_threshold_ms:
            self.slow_queries += 1
    
    def get_average_response_time(self) -> float:
        """Tempo medio risposta in ms"""
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time_ms / self.total_requests
    
    def get_error_rate(self) -> float:
        """Percentuale errori"""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100
    
    def get_requests_per_second(self) -> float:
        """Richieste al secondo (media)"""
        uptime_seconds = (datetime.utcnow() - self.created_at).total_seconds()
        if uptime_seconds == 0:
            return 0.0
        return self.total_requests / uptime_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Esporta metriche come dict"""
        return {
            "tenant_id": self.tenant_id,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "error_rate_percent": round(self.get_error_rate(), 2),
            "avg_response_time_ms": round(self.get_average_response_time(), 2),
            "requests_per_second": round(self.get_requests_per_second(), 2),
            "storage_used_mb": round(self.storage_used_bytes / (1024 * 1024), 2),
            "active_users": self.active_users,
            "total_users": self.total_users,
            "total_queries": self.total_queries,
            "slow_queries": self.slow_queries,
            "uptime_seconds": int((datetime.utcnow() - self.created_at).total_seconds())
        }


class MetricsCollector:
    """
    Collector centrale per metriche di tutti i tenant.
    Thread-safe per operazioni async.
    """
    
    def __init__(self):
        self.metrics: Dict[str, TenantMetrics] = {}
        self._lock = asyncio.Lock()
        
        # Metriche globali
        self.total_tenants = 0
        self.active_tenants = set()
        
        logger.info("MetricsCollector initialized")
    
    async def get_or_create_metrics(self, tenant_id: str) -> TenantMetrics:
        """Ottiene o crea oggetto metriche per tenant"""
        async with self._lock:
            if tenant_id not in self.metrics:
                self.metrics[tenant_id] = TenantMetrics(tenant_id)
                self.total_tenants += 1
                logger.debug(f"Created metrics for tenant: {tenant_id}")
            
            self.active_tenants.add(tenant_id)
            return self.metrics[tenant_id]
    
    async def record_request(
        self, 
        tenant_id: str,
        response_time_ms: float,
        success: bool = True
    ):
        """Registra richiesta per tenant"""
        metrics = await self.get_or_create_metrics(tenant_id)
        metrics.record_request(response_time_ms, success)
    
    async def record_query(
        self,
        tenant_id: str,
        query_time_ms: float
    ):
        """Registra query DB per tenant"""
        metrics = await self.get_or_create_metrics(tenant_id)
        metrics.record_query(query_time_ms)
    
    async def update_storage(self, tenant_id: str, bytes_used: int):
        """Aggiorna storage utilizzato"""
        metrics = await self.get_or_create_metrics(tenant_id)
        metrics.storage_used_bytes = bytes_used
    
    async def update_users(self, tenant_id: str, active: int, total: int):
        """Aggiorna contatori utenti"""
        metrics = await self.get_or_create_metrics(tenant_id)
        metrics.active_users = active
        metrics.total_users = total
    
    async def get_tenant_metrics(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Ottiene metriche per tenant specifico"""
        metrics = self.metrics.get(tenant_id)
        return metrics.to_dict() if metrics else None
    
    async def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Ottiene metriche di tutti i tenant"""
        return {
            tenant_id: metrics.to_dict()
            for tenant_id, metrics in self.metrics.items()
        }
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """Statistiche globali sistema"""
        total_requests = sum(m.total_requests for m in self.metrics.values())
        total_errors = sum(m.failed_requests for m in self.metrics.values())
        
        return {
            "total_tenants": self.total_tenants,
            "active_tenants": len(self.active_tenants),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "global_error_rate": (
                (total_errors / total_requests * 100) if total_requests > 0 else 0
            )
        }
    
    async def get_top_tenants(
        self, 
        by: str = "requests",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Top tenant per metrica specifica.
        
        Args:
            by: 'requests', 'errors', 'response_time', 'storage'
            limit: Numero massimo risultati
        """
        metrics_list = [m.to_dict() for m in self.metrics.values()]
        
        sort_keys = {
            "requests": "total_requests",
            "errors": "failed_requests",
            "response_time": "avg_response_time_ms",
            "storage": "storage_used_mb"
        }
        
        sort_key = sort_keys.get(by, "total_requests")
        
        sorted_metrics = sorted(
            metrics_list,
            key=lambda x: x[sort_key],
            reverse=True
        )
        
        return sorted_metrics[:limit]
    
    async def reset_tenant_metrics(self, tenant_id: str):
        """Reset metriche per tenant"""
        async with self._lock:
            if tenant_id in self.metrics:
                del self.metrics[tenant_id]
                logger.info(f"Reset metrics for tenant: {tenant_id}")
    
    async def reset_all_metrics(self):
        """Reset tutte le metriche"""
        async with self._lock:
            self.metrics.clear()
            self.active_tenants.clear()
            logger.info("All metrics reset")


# Middleware per tracking automatico
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware che traccia automaticamente metriche per ogni richiesta.
    """
    
    def __init__(self, app, collector: MetricsCollector):
        super().__init__(app)
        self.collector = collector
    
    async def dispatch(self, request: Request, call_next):
        # Ottieni tenant_id dal context/request
        tenant_id = request.state.tenant_id if hasattr(request.state, "tenant_id") else None
        
        if not tenant_id:
            # Skip se no tenant
            return await call_next(request)
        
        # Traccia tempo
        start_time = time.time()
        
        try:
            response = await call_next(request)
            success = response.status_code < 400
        except Exception as e:
            success = False
            raise
        finally:
            # Calcola response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Record metrics
            await self.collector.record_request(
                tenant_id,
                response_time_ms,
                success
            )
        
        return response


# Esempio di utilizzo
"""
from linkbay_multitenant.metrics import MetricsCollector, MetricsMiddleware

# Setup
metrics_collector = MetricsCollector()

# Aggiungi middleware
app.add_middleware(MetricsMiddleware, collector=metrics_collector)

# API per monitoring
@app.get("/admin/metrics/{tenant_id}")
async def get_tenant_metrics(tenant_id: str):
    return await metrics_collector.get_tenant_metrics(tenant_id)

@app.get("/admin/metrics")
async def get_all_metrics():
    return await metrics_collector.get_all_metrics()

@app.get("/admin/metrics/global")
async def global_stats():
    return await metrics_collector.get_global_stats()

@app.get("/admin/metrics/top")
async def top_tenants(by: str = "requests", limit: int = 10):
    return await metrics_collector.get_top_tenants(by, limit)

# Background task per update storage/users
async def update_tenant_stats():
    while True:
        for tenant_id in active_tenants:
            # Calcola storage
            storage = await calculate_storage(tenant_id)
            await metrics_collector.update_storage(tenant_id, storage)
            
            # Conta utenti
            active, total = await count_users(tenant_id)
            await metrics_collector.update_users(tenant_id, active, total)
        
        await asyncio.sleep(300)  # Ogni 5 minuti

@app.on_event("startup")
async def startup():
    asyncio.create_task(update_tenant_stats())
"""
