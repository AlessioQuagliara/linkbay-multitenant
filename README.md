# LinkBay-Multitenant v0.2.0

[![License](https://img.shields.io/badge/license-MIT-blue)]()
[![Python](https://img.shields.io/badge/python-3.8+-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)]()

**Sistema multitenant enterprise-ready per FastAPI - Isolamento dati, sicurezza e scalabilità**

## Caratteristiche

### Core Features
- **Multiple strategie** - Header, Subdomain, Path, JWT
- **Isolamento dati** - Database separati per tenant
- **Middleware automatico** - Identificazione tenant
- **Dipendenze FastAPI** - Accesso semplice al tenant corrente
- **Router multitenant** - Route automaticamente protette
- **Completamente async** - Performante e scalabile
- **Zero dipendenze DB** - Implementi tu i modelli

###  Enterprise Features (NEW!)
- **DB Connection Pool** - Pool dedicati per ogni tenant con auto-scaling
- **Query Security** - Interceptor che previene data leak cross-tenant
- **Async Context** - Tenant context preserved in background tasks
- **Admin API** - Gestione dinamica tenant (create, delete, update)
- **Smart Caching** - LRU cache con TTL per ridurre carico DB
- **Metrics & Monitoring** - Metriche real-time per ogni tenant
- **Data Migration** - Export, import, e migrazione tra tenant

## Installazione

```bash
pip install git+https://github.com/AlessioQuagliara/linkbay_multitenant.git
```

## Utilizzo Rapido

### 1. Implementa TenantServiceProtocol

```python
from linkbay_multitenant import TenantServiceProtocol, TenantInfo

class MyTenantService(TenantServiceProtocol):
    def __init__(self, db_session):
        self.db = db_session

    async def get_tenant_by_id(self, tenant_id: str):
        return await self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

    async def get_tenant_by_domain(self, domain: str):
        return await self.db.query(Tenant).filter(Tenant.domain == domain).first()

    # ... implementa tutti i metodi del Protocol
```

### 2. Configura nel tuo FastAPI

```python
from fastapi import FastAPI
from linkbay_multitenant import MultitenantCore, MultitenantMiddleware

app = FastAPI()

# Configurazione
tenant_service = MyTenantService(db_session)
multitenant_core = MultitenantCore(
    tenant_service=tenant_service,
    strategy="header",  # o "subdomain", "path"
    tenant_header="X-Tenant-ID"
)

# Aggiungi middleware
app.add_middleware(MultitenantMiddleware, multitenant_core=multitenant_core)
```

### 3. Usa il Router Multitenant

```python
from linkbay_multitenant import MultitenantRouter, require_tenant

router = MultitenantRouter(prefix="/api", tags=["api"])

@router.get("/data")
async def get_tenant_data(tenant = Depends(require_tenant)):
    return {"tenant_id": tenant.id, "data": "solo per questo tenant"}

app.include_router(router.router)
```

### 4. Dipendenze Disponibili

```python
from linkbay_multitenant import get_tenant, get_tenant_id, require_tenant

@app.get("/info")
async def tenant_info(tenant = Depends(get_tenant)):
    return tenant

@app.get("/protected")
async def protected_data(tenant = Depends(require_tenant)):
    return f"Dati per {tenant.name}"
```

## Strategie di Identificazione

### Header (default)
```http
GET /api/data
X-Tenant-ID: tenant-123
```

### Subdomain
```http
GET /api/data
Host: tenant-123.yourapp.com
```

### Path
```http
GET /tenant-123/api/data
```

## Esempio Completo

```python
from fastapi import FastAPI, Depends
from linkbay_multitenant import (
    MultitenantCore, MultitenantMiddleware, 
    MultitenantRouter, require_tenant
)

app = FastAPI()

# Setup
tenant_service = MyTenantService()
multitenant_core = MultitenantCore(tenant_service, strategy="header")
app.add_middleware(MultitenantMiddleware, multitenant_core=multitenant_core)

# Router con tenant
router = MultitenantRouter()

@router.get("/products")
async def get_products(tenant = Depends(require_tenant)):
    # Qui query DB filtrata per tenant
    return {"tenant": tenant.id, "products": []}

app.include_router(router.router)
```

## 🏢 Enterprise Features - Guida Completa

### 1. DB Connection Pool

Pool di connessioni dedicato per ogni tenant con configurazione ottimizzata:

```python
from linkbay_multitenant import TenantDBPool

# Setup pool
def get_tenant_db_url(tenant_id: str) -> str:
    return f"postgresql+asyncpg://user:pass@localhost/tenant_{tenant_id}"

db_pool = TenantDBPool(
    get_tenant_db_url,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30
)

# Usa in route
@app.get("/data")
async def get_data(tenant = Depends(require_tenant)):
    async with await db_pool.get_session(tenant.id) as session:
        result = await session.execute(select(Product))
        return result.scalars().all()

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown():
    await db_pool.close_all()

# Monitoring pool
stats = db_pool.get_all_stats()
```

### 2. Query Security Interceptor

Previene accidentali data leak verificando filtri tenant:

```python
from linkbay_multitenant import TenantQueryInterceptor, TenantQueryBuilder

# Setup interceptor
interceptor = TenantQueryInterceptor(
    tenant_column_name="tenant_id",
    strict_mode=True,
    exempt_tables={"system_config", "migrations"}
)

# Registra con engine
interceptor.register_with_async_engine(engine)

# Query builder sicuro
@app.get("/products")
async def get_products(tenant = Depends(require_tenant), session = Depends(get_db)):
    builder = TenantQueryBuilder(tenant.id)
    query = session.query(Product)
    query = builder.filter_query(query)  # Filtro automatico
    return query.all()

# Operazioni admin (bypass temporaneo)
from linkbay_multitenant import AdminQueryContext

with AdminQueryContext(interceptor):
    all_tenants = session.query(Tenant).all()  # ✅ Senza filtri
```

### 3. Async Context Management

Context tenant preservato in background tasks:

```python
from linkbay_multitenant import TenantContext, run_with_tenant_context

# Il middleware imposta automaticamente il context

@app.get("/data")
async def get_data():
    tenant_id = TenantContext.get_tenant_id()  # ✅ Disponibile ovunque
    return {"tenant": tenant_id}

# Background tasks con context preserved
async def send_email(to: str):
    tenant_id = TenantContext.require_tenant_id()  # ✅ Context preserved
    logger.info(f"Sending email for tenant {tenant_id}")

@app.post("/send")
async def trigger_email(background_tasks: BackgroundTasks):
    tenant_id = TenantContext.get_tenant_id()
    background_tasks.add_task(
        run_with_tenant_context,
        tenant_id,
        send_email("user@example.com")
    )
```

### 4. Admin API

Gestione completa tenant via API:

```python
from linkbay_multitenant import TenantAdminService, create_admin_router

# Setup service
admin_service = TenantAdminService(db_pool=db_pool)

# Auth admin (implementa la tua logica)
async def require_admin_auth():
    # Verifica token/permissions
    pass

# Registra router
admin_router = create_admin_router(admin_service, require_admin_auth)
app.include_router(admin_router)

# API disponibili:
# POST   /admin/tenants          - Crea tenant
# GET    /admin/tenants          - Lista tenant
# GET    /admin/tenants/{id}     - Dettagli
# PATCH  /admin/tenants/{id}     - Aggiorna
# DELETE /admin/tenants/{id}     - Elimina
```

### 5. Smart Caching

Cache LRU con TTL per performance ottimali:

```python
from linkbay_multitenant import TenantCache, TenantCacheService, cache_cleanup_task

# Setup cache
cache = TenantCache(
    max_size=1000,
    ttl_seconds=300,  # 5 minuti
    enable_stats=True
)

# Service con cache-aside pattern
async def get_tenant_from_db(tenant_id: str):
    return await db.get_tenant(tenant_id)

cache_service = TenantCacheService(cache, get_tenant_from_db)

# Usa in dependency
async def get_tenant_cached(tenant_id: str = Depends(get_tenant_id)):
    return await cache_service.get_tenant(tenant_id)

# Background cleanup
@app.on_event("startup")
async def startup():
    asyncio.create_task(cache_cleanup_task(cache, interval_seconds=60))

# Invalida dopo update
@app.put("/admin/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, data: TenantUpdate):
    await db.update_tenant(tenant_id, data)
    await cache_service.invalidate_tenant(tenant_id)

# Monitoring
@app.get("/admin/cache/stats")
async def cache_stats():
    return cache.get_stats()
```

### 6. Metrics & Monitoring

Tracciamento real-time metriche per tenant:

```python
from linkbay_multitenant import MetricsCollector, MetricsMiddleware

# Setup
metrics_collector = MetricsCollector()

# Middleware automatico
app.add_middleware(MetricsMiddleware, collector=metrics_collector)

# API monitoring
@app.get("/admin/metrics/{tenant_id}")
async def get_tenant_metrics(tenant_id: str):
    return await metrics_collector.get_tenant_metrics(tenant_id)

@app.get("/admin/metrics/global")
async def global_stats():
    return await metrics_collector.get_global_stats()

@app.get("/admin/metrics/top")
async def top_tenants(by: str = "requests", limit: int = 10):
    # by: "requests", "errors", "response_time", "storage"
    return await metrics_collector.get_top_tenants(by, limit)

# Metriche incluse:
# - Total requests & errors
# - Average response time
# - Requests per second
# - Storage used
# - Active/total users
# - DB queries & slow queries
```

### 7. Data Migration

Sistema completo per migrazione dati:

```python
from linkbay_multitenant import TenantMigrationService, create_migration_router

# Setup service
migration_service = TenantMigrationService(
    db_pool=db_pool,
    export_path="/var/tenant_exports"
)

# Registra router
migration_router = create_migration_router(migration_service, require_admin_auth)
app.include_router(migration_router)

# Uso programmatico

# 1. Migra tutto da tenant A a B
job_id = await migration_service.migrate_tenant_data(
    "tenant-a",
    "tenant-b",
    copy_mode=False  # False = sposta, True = copia
)

# 2. Copia solo alcune tabelle
job_id = await migration_service.migrate_tenant_data(
    "tenant-a",
    "tenant-b",
    tables=["users", "products"],
    copy_mode=True
)

# 3. Export per backup
export_file = await migration_service.export_tenant_data("tenant-a")

# 4. Monitor progresso
status = await migration_service.get_job_status(job_id)
# {
#   "status": "running",
#   "progress_percent": 45.2,
#   "migrated_records": 1234,
#   "total_records": 2730
# }
```

## 📋 Setup Completo Enterprise

```python
from fastapi import FastAPI
from linkbay_multitenant import (
    MultitenantCore,
    MultitenantMiddleware,
    TenantDBPool,
    TenantQueryInterceptor,
    TenantCache,
    MetricsCollector,
    MetricsMiddleware,
    TenantAdminService,
    create_admin_router
)

app = FastAPI()

# 1. Core multitenant
tenant_service = MyTenantService()
multitenant_core = MultitenantCore(tenant_service, strategy="header")
app.add_middleware(MultitenantMiddleware, multitenant_core=multitenant_core)

# 2. DB Pool
db_pool = TenantDBPool(get_tenant_db_url, pool_size=10)

# 3. Security interceptor
interceptor = TenantQueryInterceptor(strict_mode=True)
interceptor.register_with_async_engine(engine)

# 4. Caching
cache = TenantCache(max_size=1000, ttl_seconds=300)

# 5. Metrics
metrics_collector = MetricsCollector()
app.add_middleware(MetricsMiddleware, collector=metrics_collector)

# 6. Admin API
admin_service = TenantAdminService(db_pool=db_pool)
admin_router = create_admin_router(admin_service, require_admin_auth)
app.include_router(admin_router)

# Cleanup
@app.on_event("shutdown")
async def shutdown():
    await db_pool.close_all()
```

## 🎯 Production Checklist

- ✅ DB Connection pooling configurato
- ✅ Query interceptor attivo (strict_mode=True)
- ✅ Caching implementato per tenant info
- ✅ Metrics collector attivo
- ✅ Admin API protette con autenticazione
- ✅ Background tasks usano context management
- ✅ Migration strategy definita
- ✅ Monitoring dashboard setup
- ✅ Rate limiting per tenant
- ✅ Backup automatici configurati

## Licenza
```bash
MIT - Vedere LICENSE per dettagli.
```

## ESEMPIO BASE

```python
from fastapi import FastAPI, Depends
from linkbay_multitenant import (
    MultitenantCore, MultitenantMiddleware, 
    MultitenantRouter, require_tenant
)

app = FastAPI()

# Configurazione
tenant_service = MyTenantService()  # La tua implementazione
multitenant_core = MultitenantCore(
    tenant_service=tenant_service,
    strategy="subdomain"  # o "header", "path"
)

# Middleware automatico
app.add_middleware(MultitenantMiddleware, multitenant_core=multitenant_core)

# Router multitenant
router = MultitenantRouter(prefix="/api")

@router.get("/dashboard")
async def dashboard(tenant = Depends(require_tenant)):
    return {
        "tenant": tenant.name,
        "message": f"Benvenuto nel tenant {tenant.id}"
    }

app.include_router(router.router)
```
