# LinkBay-Multitenant Beta 1.0.0

[![License](https://img.shields.io/badge/license-MIT-blue)]()

**Sistema multitenant semplice e scalabile per FastAPI - Isolamento dati e routing per tenant**

## Caratteristiche

- **Multiple strategie** - Header, Subdomain, Path, JWT
- **Isolamento dati** - Database separati per tenant
- **Middleware automatico** - Identificazione tenant
- **Dipendenze FastAPI** - Accesso semplice al tenant corrente
- **Router multitenant** - Route automaticamente protette
- **Completamente async** - Performante e scalabile
- **Zero dipendenze DB** - Implementi tu i modelli

## Installazione

```bash
pip install git+https://github.com/AlessioQuagliara/linkbay-multitenant.git
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

## Licenza
```bash
MIT - Vedere LICENSE per dettagli.
```

## ESEMPIO

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
