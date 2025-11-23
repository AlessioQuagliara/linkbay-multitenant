"""
Esempio completo di setup enterprise LinkBay-Multitenant.
Mostra tutte le features: DB Pool, Security, Cache, Metrics, Admin API.
"""
from fastapi import FastAPI, Depends, HTTPException, Header
from contextlib import asynccontextmanager
import asyncio
import logging

from linkbay_multitenant import (
    # Core
    MultitenantCore,
    MultitenantMiddleware,
    MultitenantRouter,
    require_tenant,
    get_tenant_id,
    TenantServiceProtocol,
    TenantInfo,
    
    # Enterprise
    TenantDBPool,
    TenantQueryInterceptor,
    TenantContext,
    TenantCache,
    TenantCacheService,
    cache_cleanup_task,
    MetricsCollector,
    MetricsMiddleware,
    TenantAdminService,
    create_admin_router,
    TenantMigrationService,
    create_migration_router,
)

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ========================================
# 1. Implementa TenantServiceProtocol
# ========================================

class MyTenantService(TenantServiceProtocol):
    """Implementazione del service tenant (usa il tuo DB)"""
    
    def __init__(self):
        # Mock data per demo
        self.tenants = {
            "tenant-1": {
                "id": "tenant-1",
                "name": "Acme Corp",
                "domain": "acme.example.com",
                "subdomain": "acme",
                "is_active": True,
                "database_url": "postgresql://localhost/tenant_1"
            },
            "tenant-2": {
                "id": "tenant-2",
                "name": "Beta Inc",
                "domain": "beta.example.com",
                "subdomain": "beta",
                "is_active": True,
                "database_url": "postgresql://localhost/tenant_2"
            }
        }
    
    async def get_tenant_by_id(self, tenant_id: str):
        return self.tenants.get(tenant_id)
    
    async def get_tenant_by_domain(self, domain: str):
        for tenant in self.tenants.values():
            if tenant.get("domain") == domain:
                return tenant
        return None
    
    async def get_tenant_by_subdomain(self, subdomain: str):
        for tenant in self.tenants.values():
            if tenant.get("subdomain") == subdomain:
                return tenant
        return None
    
    async def get_tenant_database_url(self, tenant_id: str) -> str:
        tenant = await self.get_tenant_by_id(tenant_id)
        return tenant.get("database_url") if tenant else None


# ========================================
# 2. Setup Enterprise Components
# ========================================

# Tenant service
tenant_service = MyTenantService()

# DB Pool
def get_tenant_db_url(tenant_id: str) -> str:
    return f"postgresql+asyncpg://user:pass@localhost/tenant_{tenant_id}"

db_pool = TenantDBPool(
    get_tenant_db_url,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600
)

# Query Security Interceptor
query_interceptor = TenantQueryInterceptor(
    tenant_column_name="tenant_id",
    strict_mode=True,
    exempt_tables={"system_config", "alembic_version"}
)

# Caching
tenant_cache = TenantCache(
    max_size=1000,
    ttl_seconds=300,
    enable_stats=True
)

async def get_tenant_from_db(tenant_id: str):
    return await tenant_service.get_tenant_by_id(tenant_id)

cache_service = TenantCacheService(tenant_cache, get_tenant_from_db)

# Metrics
metrics_collector = MetricsCollector()

# Admin Services
admin_service = TenantAdminService(db_pool=db_pool)
migration_service = TenantMigrationService(
    db_pool=db_pool,
    export_path="/tmp/tenant_exports"
)


# ========================================
# 3. Admin Authentication
# ========================================

async def require_admin_auth(x_admin_token: str = Header(...)):
    """Verifica token admin (implementa la tua logica)"""
    if x_admin_token != "admin-secret-token":
        raise HTTPException(401, "Invalid admin token")


# ========================================
# 4. FastAPI App Setup
# ========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestione lifecycle app"""
    # Startup
    logger.info("Starting enterprise multitenant app...")
    
    # Avvia cleanup task per cache
    cleanup_task = asyncio.create_task(
        cache_cleanup_task(tenant_cache, interval_seconds=60)
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    cleanup_task.cancel()
    await db_pool.close_all()


app = FastAPI(
    title="LinkBay Multitenant Enterprise",
    version="1.0.0-beta",
    lifespan=lifespan
)

# Core multitenant
multitenant_core = MultitenantCore(
    tenant_service=tenant_service,
    strategy="header",
    tenant_header="X-Tenant-ID"
)

# Middleware
app.add_middleware(MultitenantMiddleware, multitenant_core=multitenant_core)
app.add_middleware(MetricsMiddleware, collector=metrics_collector)


# ========================================
# 5. Dependency con Cache
# ========================================

async def get_tenant_cached(tenant_id: str = Depends(get_tenant_id)):
    """Ottiene tenant con caching"""
    return await cache_service.get_tenant(tenant_id)


# ========================================
# 6. Routes Tenant
# ========================================

# Router multitenant
mt_router = MultitenantRouter(prefix="/api", tags=["tenant"])

@mt_router.get("/dashboard")
async def dashboard(tenant = Depends(require_tenant)):
    """Dashboard tenant con metrics"""
    metrics = await metrics_collector.get_tenant_metrics(tenant.id)
    
    return {
        "tenant": {
            "id": tenant.id,
            "name": tenant.name
        },
        "metrics": metrics
    }

@mt_router.get("/products")
async def get_products(tenant = Depends(require_tenant)):
    """Lista prodotti tenant (usa DB pool)"""
    # Esempio con DB pool
    # async with await db_pool.get_session(tenant.id) as session:
    #     result = await session.execute(select(Product))
    #     return result.scalars().all()
    
    return {
        "tenant_id": tenant.id,
        "products": ["demo-product-1", "demo-product-2"]
    }

@mt_router.get("/info")
async def tenant_info(tenant = Depends(get_tenant_cached)):
    """Info tenant con caching"""
    return {
        "tenant": tenant,
        "context_tenant_id": TenantContext.get_tenant_id()
    }

app.include_router(mt_router.router)


# ========================================
# 7. Admin Routes
# ========================================

# Admin tenant management
admin_router = create_admin_router(admin_service, require_admin_auth)
app.include_router(admin_router)

# Migration management
migration_router = create_migration_router(migration_service, require_admin_auth)
app.include_router(migration_router)

# Cache stats
@app.get("/admin/cache/stats", tags=["admin"])
async def cache_stats(x_admin_token: str = Header(...)):
    await require_admin_auth(x_admin_token)
    return tenant_cache.get_stats()

# Global metrics
@app.get("/admin/metrics/global", tags=["admin"])
async def global_metrics(x_admin_token: str = Header(...)):
    await require_admin_auth(x_admin_token)
    return await metrics_collector.get_global_stats()

# Top tenants
@app.get("/admin/metrics/top", tags=["admin"])
async def top_tenants(
    by: str = "requests",
    limit: int = 10,
    x_admin_token: str = Header(...),
):
    await require_admin_auth(x_admin_token)
    return await metrics_collector.get_top_tenants(by, limit)

# DB Pool stats
@app.get("/admin/db-pool/stats", tags=["admin"])
async def db_pool_stats(x_admin_token: str = Header(...)):
    await require_admin_auth(x_admin_token)
    return db_pool.get_all_stats()


# ========================================
# 8. Health Check
# ========================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "cache_size": len(tenant_cache._cache),
        "active_db_pools": len(db_pool.pools),
        "metrics_tracked": len(metrics_collector.metrics)
    }


# ========================================
# 9. Root
# ========================================

@app.get("/")
async def root():
    """Root endpoint con informazioni sistema"""
    return {
        "app": "LinkBay Multitenant Enterprise",
        "version": "1.0.0-beta",
        "features": [
            "DB Connection Pool",
            "Query Security",
            "Smart Caching",
            "Metrics & Monitoring",
            "Admin API",
            "Data Migration",
            "Async Context Management"
        ],
        "endpoints": {
            "tenant": "/api/*",
            "admin": "/admin/*",
            "health": "/health",
            "docs": "/docs"
        }
    }


# ========================================
# Come usare questo esempio:
# ========================================
"""
1. Installa dipendenze:
   pip install linkbay-multitenant fastapi uvicorn

2. Avvia server:
   uvicorn example_enterprise:app --reload

3. Test con tenant:
   curl -H "X-Tenant-ID: tenant-1" http://localhost:8000/api/dashboard

4. Admin API (usa token):
   curl -H "X-Admin-Token: admin-secret-token" http://localhost:8000/admin/tenants

5. Metrics:
   curl -H "X-Admin-Token: admin-secret-token" http://localhost:8000/admin/metrics/global

6. Cache stats:
   curl -H "X-Admin-Token: admin-secret-token" http://localhost:8000/admin/cache/stats

7. Docs interattive:
   http://localhost:8000/docs
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("example_enterprise:app", host="0.0.0.0", port=8000, reload=True)
