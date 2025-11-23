# LinkBay-MultiTenant Beta 1.0.0

Sistema leggero di multi-tenancy per FastAPI.

## Installazione

```bash
pip install git+https://github.com/AlessioQuagliara/linkbay-multitenant.git
```

## Quick Start

### 1. Implementa TenantServiceProtocol

```python
from linkbay_multitenant import TenantServiceProtocol, TenantContext

class MyTenantService:
    async def get_tenant_context(self, tenant_id: str) -> TenantContext:
        tenant = await db.query(Tenant).filter_by(id=tenant_id).first()
        return TenantContext(
            tenant_id=tenant.id,
            schema_name=f"tenant_{tenant.id}"
        )
```

### 2. Configura il plugin

```python
from fastapi import FastAPI
from linkbay_multitenant import LinkBayMultiTenantPlugin, MultiTenantConfig

app = FastAPI()

config = MultiTenantConfig(tenant_service=MyTenantService())
plugin = LinkBayMultiTenantPlugin(config)
plugin.install(app)
```

### 3. Usa nei tuoi endpoint

```python
from fastapi import Depends
from linkbay_multitenant import get_tenant_context

@app.get("/api/data")
async def get_data(tenant = Depends(get_tenant_context)):
    return {"tenant_id": tenant.tenant_id}
```

### 4. Test

```bash
curl http://localhost:8000/api/data -H "X-Tenant-ID: tenant1"
```

## Struttura

```
linkbay-multitenant/
├── __init__.py
├── plugin.py
├── schemas.py
├── service.py
└── dependencies.py
```

## Configurazione

```python
@dataclass
class MultiTenantConfig:
    tenant_service: TenantServiceProtocol
    identification_method: TenantIdentificationMethod = HEADER  # o SUBDOMAIN, COOKIE
    header_name: str = "X-Tenant-ID"
    require_tenant: bool = True
```

## License

MIT
