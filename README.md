# LinkBay-Multitenant v0.2.1

[![License](https://img.shields.io/badge/license-MIT-blue)]()
[![Python](https://img.shields.io/badge/python-3.8+-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)]()

LinkBay-Multitenant è una raccolta di moduli **semplici da usare** per costruire API multi-tenant con FastAPI. Offre una base core leggera e una serie di estensioni opzionali per scenari enterprise. Tutti gli esempi che vedi in questa pagina sono completi e riproducibili.

> **Idea chiave**: parti dal core (middleware + router) e abilita solo i moduli di cui hai davvero bisogno. Ogni sezione indica chiaramente cosa fa il modulo, quando usarlo e quali limiti ha.

---

## 1. Installazione

```bash
pip install git+https://github.com/AlessioQuagliara/linkbay_multitenant.git@main
```

Oppure, per sviluppo locale:

```bash
git clone https://github.com/AlessioQuagliara/linkbay_multitenant.git
cd linkbay_multitenant
pip install -e .
```

---

## 2. Core in tre step

### Step 1 – TenantService

```python
from linkbay_multitenant import TenantServiceProtocol

class MyTenantService(TenantServiceProtocol):
    async def get_tenant_by_id(self, tenant_id: str):
        # Sostituisci con il tuo storage
        return await TenantTable.get(tenant_id)

    async def get_tenant_by_domain(self, domain: str):
        return await TenantTable.get_by_domain(domain)

    async def get_tenant_by_subdomain(self, subdomain: str):
        return await TenantTable.get_by_subdomain(subdomain)

    async def get_tenant_database_url(self, tenant_id: str) -> str:
        return f"postgresql+asyncpg://user:pass@localhost/{tenant_id}"
```

### Step 2 – Core + Middleware

```python
from fastapi import FastAPI
from linkbay_multitenant import MultitenantCore, MultitenantMiddleware

tenant_service = MyTenantService()
core = MultitenantCore(
    tenant_service=tenant_service,
    strategy="header",          # "header" | "subdomain" | "path"
    tenant_header="X-Tenant-ID"
)

app = FastAPI()
app.add_middleware(MultitenantMiddleware, multitenant_core=core)
```

### Step 3 – Router e dipendenze

```python
from fastapi import Depends
from linkbay_multitenant import MultitenantRouter, require_tenant

router = MultitenantRouter(prefix="/api", tags=["api"])

@router.get("/dashboard")
async def dashboard(tenant = Depends(require_tenant)):
    return {"tenant": tenant.id, "message": "Benvenuto!"}

app.include_router(router.router)
```

**Già pronto!** Con questi tre passi hai isolamento logico per tenant, middleware automatico e dipendenze riutilizzabili.

---

## 3. Moduli opzionali (usa solo ciò che ti serve)

| Modulo | Quando usarlo | File | Esempio rapido |
|--------|----------------|------|----------------|
| `TenantDBPool` | Tenant con database dedicato | `linkbay_multitenant/db_pool.py` | [Pool & lifecycle](#tenantdbpool--gestione-connessioni) |
| `TenantQueryInterceptor` | Vuoi enforcement sui filtri tenant | `linkbay_multitenant/security.py` | [Query interceptor](#tenantqueryinterceptor--sicurezza-query) |
| `TenantContext` | Preservare tenant in background tasks | `linkbay_multitenant/context.py` | [Context async/sync](#tenantcontext--contextvars-semplici) |
| `TenantCache` | Ridurre letture su tenant info | `linkbay_multitenant/cache.py` | [Cache & invalidazione](#tenantcache--cache-con-invalidazione) |
| `MetricsCollector` | Mettere metriche basiche in memoria | `linkbay_multitenant/metrics.py` | [Metriche e export](#metricscollector--metriche-semplici) |
| `TenantAdminService` | Esporre CRUD tenant | `linkbay_multitenant/admin.py` | [Admin API](#tenantadminservice--admin-api) |
| `TenantMigrationService` | Coordinare export/import/move | `linkbay_multitenant/migration.py` | [Migrazioni](#tenantmigrationservice--migrazioni-guidate) |

Le sezioni seguenti spiegano ogni modulo, i limiti e come integrarli in deployment reali.

---

## TenantDBPool – Gestione connessioni

**Use case**: ogni tenant ha un database (o schema) dedicato.

```python
from linkbay_multitenant import TenantDBPool

def get_db_url(tenant_id: str) -> str:
    return f"postgresql+asyncpg://user:pass@db/{tenant_id}"

db_pool = TenantDBPool(
    get_tenant_db_url=get_db_url,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
)

@router.get("/orders")
async def list_orders(tenant = Depends(require_tenant)):
    async with await db_pool.get_session(tenant.id) as session:
        rows = await session.execute(select(Order))
        return rows.scalars().all()

@app.on_event("shutdown")
async def shutdown():
    await db_pool.close_all()
```

**Lifecycle quando elimini un tenant**

```python
await db_pool.close_tenant_pool("tenant-123")
```

- Chiude nuove connessioni subito.
- Connessioni in-flight sono lasciate terminare (usa timeouts del driver). Se vuoi un drain esplicito, chiama `await asyncio.sleep(grace_period)` prima di droppare il database.
- Documenta ai tuoi utenti che le DELETE tenant sono operazioni amministrative pianificate.

**Pattern shared database**

Se preferisci un database condiviso:

1. Non usare il pool per tenant singoli.
2. Affidati al query interceptor (o Row Level Security lato DB).
3. Mantieni un’unica engine SQLAlchemy e passa `tenant_id` nei filtri.

---

## TenantQueryInterceptor – Sicurezza query

**Obiettivo**: bloccare query senza filtro tenant.

```python
from linkbay_multitenant import TenantQueryInterceptor

interceptor = TenantQueryInterceptor(
    tenant_column_name="tenant_id",
    strict_mode=True,
    exempt_tables={"system_config", "alembic_version"},
)

interceptor.register_with_async_engine(engine)
```

### Limitazioni e best practice

- **JOIN**: l'interceptor cerca `WHERE ... tenant_id =` nel SQL finale. Se fai join tra tabelle tenant-aware e tabelle globali, assicurati che almeno una condizione `tenant_id` sia presente. Usa alias espliciti:

  ```python
  query = select(Order).join(Customer).where(Order.tenant_id == tenant_id)
  ```

- **Subquery / CTE**: il controllo è testuale; se il filtro è in una subquery ma non nella query esterna, potresti ricevere un falso positivo. Suggerimento: forza sempre il filtro nella query esterna.

- **Bulk UPDATE/DELETE**: devi aggiungere manualmente il filtro tenant:

  ```python
  await session.execute(
      update(Product).where(Product.tenant_id == tenant_id).values(price=10)
  )
  ```

- **Operazioni admin**: usa il context manager per bypass controllato.

  ```python
  from linkbay_multitenant import AdminQueryContext

  with AdminQueryContext(interceptor):
      await session.execute(update(SystemSetting).values(...))
  ```

- **Logging**: l'interceptor logga ogni blocco in `logger.error`. Configura un handler dedicato e invia alert (es. Slack) su tentativi ripetuti.

---

## TenantContext – ContextVars semplici

Gestisce `tenant_id` anche in background tasks.

```python
from linkbay_multitenant import TenantContext, run_with_tenant_context

@router.post("/email")
async def send(background_tasks: BackgroundTasks, tenant = Depends(require_tenant)):
    background_tasks.add_task(
        run_with_tenant_context,
        tenant.id,
        send_email
    )

async def send_email():
    tenant_id = TenantContext.require_tenant_id()
```

### Codice sync e thread pool

- Le contextvars funzionano anche dentro `loop.run_in_executor`. Se usi librerie sincrone, avvolgi la chiamata:

  ```python
  def sync_task():
      tenant_id = TenantContext.require_tenant_id()
      ...

  await run_in_executor(None, sync_task)
  ```

- In worker separati (Celery, RQ) passa `tenant_id` come argomento e richiama `TenantContext.set_tenant_id` all'inizio del task.

---

## TenantCache – Cache con invalidazione

```python
from linkbay_multitenant import TenantCache, TenantCacheService

cache = TenantCache(max_size=1000, ttl_seconds=300)

async def fetch_tenant(tenant_id: str):
    return await tenant_service.get_tenant_by_id(tenant_id)

cache_service = TenantCacheService(cache, fetch_tenant)

async def get_tenant_cached(tenant_id = Depends(get_tenant_id)):
    return await cache_service.get_tenant(tenant_id)
```

### Invalidazione distribuita (multi-pod)

Il modulo è in-memory. Per deployment multi-container:

1. **Sostituisci** `TenantCache` con Redis o Memcached. Esempio Redis:

   ```python
   import aioredis

   redis = aioredis.from_url("redis://cache:6379")

   async def redis_cache_get(tenant_id):
       data = await redis.get(f"tenant:{tenant_id}")
       return json.loads(data) if data else None
   ```

2. Usa un canale Pub/Sub per invalidazioni:

   ```python
   await redis.publish("tenant-invalidate", tenant_id)
   ```

3. Ogni istanza ascolta il canale e chiama `cache.delete(tenant_id)`.

---

## MetricsCollector – Metriche semplici

Pensato per ambienti di test o istanze singole.

```python
from linkbay_multitenant import MetricsCollector, MetricsMiddleware

collector = MetricsCollector()
app.add_middleware(MetricsMiddleware, collector=collector)

@app.get("/admin/metrics/{tenant_id}")
async def tenant_metrics(tenant_id: str, admin = Depends(require_admin)):
    return await collector.get_tenant_metrics(tenant_id)
```

### Produzione & storicizzazione

- Le metriche sono in-memory → si azzerano a ogni riavvio.
- Per ambienti multi-istanzia integra Prometheus:

  ```python
  from prometheus_client import Counter

  REQUESTS = Counter("tenant_requests", "Requests per tenant", ["tenant"])

  await collector.record_request(tenant.id, response_time)
  REQUESTS.labels(tenant=tenant.id).inc()
  ```

- Altre opzioni: OpenTelemetry + OTLP exporter, InfluxDB, Timescale.

---

## TenantAdminService – Admin API

```python
from linkbay_multitenant import TenantAdminService, create_admin_router

admin_service = TenantAdminService(db_pool=db_pool)

async def require_admin(token: str = Header(...)):
    if token != "secret":
        raise HTTPException(401)

app.include_router(create_admin_router(admin_service, require_admin))
```

### Workflow di onboarding

1. **POST /admin/tenants** – valida i dati.
2. Nel service implementa:
   - creazione schema/database
   - esecuzione migrazioni (vedi sezione successiva)
   - popolamento dati iniziali
3. **Health check**: dopo la creazione prova una query `SELECT 1` usando `TenantDBPool`.

---

## TenantMigrationService – Migrazioni guidate

```python
from linkbay_multitenant import TenantMigrationService, create_migration_router

migration_service = TenantMigrationService(db_pool=db_pool)
app.include_router(create_migration_router(migration_service, require_admin))
```

### Safety checklist

- Export/import avviene tabella per tabella → non è una transazione globale.
- Se la migrazione fallisce a metà, i record già importati restano. Prevedi un backup.
- Per un **dry-run**, chiama `export_tenant_data` e controlla il JSON senza importarlo.
- Usa `copy_mode=True` per copiare senza cancellare il sorgente.
- Implementa `_delete_source_data` solo se hai bisogno di move.
- Aggiungi validazioni personalizzate (es. confronta numero record prima/dopo).

---

## Rate limiting per tenant

La libreria non include un limiter, ma puoi collegarne uno in 5 righe con `slowapi` o `starlette-limiter`.

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=lambda request: (TenantContext.get_tenant_id(), get_remote_address(request)))

@app.get("/api/data")
@limiter.limit("100/minute")
async def data(...):
    ...
```

In alternativa, usa API Gateway (Kong, APISIX) e passa `tenant_id` nell’header.

---

## Monitoraggio & logging del Query Interceptor

- Configura un logger dedicato:

  ```python
  logger = logging.getLogger("linkbay_multitenant.security")
  logger.setLevel(logging.WARNING)
  ```

- Invia gli eventi critici a un SIEM (Splunk, Datadog) o a Slack.
- Monitora `has_tenant_filter` per capire se hai query sospette ricorrenti.
- Se noti performance issue, valuta l’uso di viste/materialized view con filtro tenant pre-applicato.

---

## Schema migrations per N tenant

### Database per tenant

1. Conserva la lista tenant in un’unica tabella master.
2. Usa Alembic con uno script custom:

   ```bash
   alembic upgrade head --sql > migration.sql
   for tenant in $(python list_tenants.py); do
       psql $tenant < migration.sql
   done
   ```

3. Prevedi rollback per tenant falliti (backup + ripristino).

### Shared database

- Usa una singola migrazione che aggiunge colonne/constraint multi-tenant.
- Abilita Row Level Security o il query interceptor.

---

## Scelte architetturali

| Scenario | Suggerimento |
|----------|--------------|
| Pochi tenant con dati pesanti | Database per tenant con `TenantDBPool` |
| Molti tenant “small” | Database condiviso, query interceptor + RLS |
| Migrazione da single-tenant | Inizia con `header strategy` e copia i dati tenant per tenant |

Scegli il modello più semplice che soddisfa i tuoi requisiti operativi.

---

## Esempio completo

Per vedere tutto funzionare assieme, apri `example_enterprise.py`. È un’app FastAPI completa con middleware, admin API, cache, metriche e migrazioni.

```bash
uvicorn example_enterprise:app --reload
```

---

## Licenza

```bash
MIT - vedere LICENSE
```

---

## Supporto

- Issues: https://github.com/AlessioQuagliara/linkbay_multitenant/issues
- Email: quagliara.alessio@gmail.com

Contribuisci, apri una issue o raccontaci come stai usando la libreria 🧡
