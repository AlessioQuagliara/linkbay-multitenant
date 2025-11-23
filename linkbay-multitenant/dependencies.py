from fastapi import Depends, HTTPException, status, Request
from typing import Optional
from .schemas import TenantInfo

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

async def get_tenant_db(
    tenant: TenantInfo = Depends(require_tenant)
):
    """Dipendenza per ottenere la connessione DB del tenant"""
    # Qui implementerai la logica per ottenere il DB del tenant specifico
    # Esempio: return get_database_connection(tenant.database_config)
    return f"Database connection for tenant: {tenant.id}"