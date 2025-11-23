from fastapi import Depends, HTTPException, status, Request
from typing import Optional, Protocol
from .schemas import TenantInfo

# Protocol per il servizio database tenant
class DatabaseServiceProtocol(Protocol):
    async def get_tenant_database(self, tenant_id: str): ...

async def get_tenant(request: Request) -> Optional[TenantInfo]:
    """Dipendenza per ottenere le info del tenant corrente"""
    return getattr(request.state, "tenant", None)

async def get_tenant_id(request: Request) -> Optional[str]:
    """Dipendenza per ottenere l'ID del tenant corrente"""
    return getattr(request.state, "tenant_id", None)

async def require_tenant(
    tenant: Optional[TenantInfo] = Depends(get_tenant)
) -> TenantInfo:
    """Dipendenza che richiede un tenant valido"""
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant non specificato o non valido"
        )
    return tenant

# DIPENDENZA VUOTA - TU LA IMPLEMENTI NEL TUO CMS
async def get_tenant_db(
    tenant: TenantInfo = Depends(require_tenant)
):
    """
    DIPENDENDA VUOTA - Implementala nel tuo CMS:
    
    Esempio nel tuo codice:
    
    async def get_tenant_db(tenant: TenantInfo = Depends(require_tenant)):
        # Tua logica per connetterti al DB del tenant
        database_url = f"postgresql://.../tenant_{tenant.id}"
        return await get_database_connection(database_url)
    """
    raise NotImplementedError(
        "Implementa get_tenant_db nel tuo CMS con la tua logica database"
    )