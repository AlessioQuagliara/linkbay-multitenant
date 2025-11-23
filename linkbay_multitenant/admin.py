"""
API Admin per gestione dinamica dei tenant.
Creazione, eliminazione, configurazione tenant.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Schemas Pydantic
class TenantCreate(BaseModel):
    """Schema per creazione nuovo tenant"""
    name: str = Field(..., min_length=1, max_length=100)
    domain: Optional[str] = Field(None, max_length=255)
    subdomain: Optional[str] = Field(None, max_length=63)
    database_name: Optional[str] = None
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Acme Corp",
                "domain": "acme.com",
                "subdomain": "acme",
                "config": {
                    "max_users": 100,
                    "features": ["analytics", "api_access"]
                }
            }
        }


class TenantUpdate(BaseModel):
    """Schema per aggiornamento tenant"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    domain: Optional[str] = Field(None, max_length=255)
    subdomain: Optional[str] = Field(None, max_length=63)
    is_active: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class TenantResponse(BaseModel):
    """Schema risposta tenant"""
    id: str
    name: str
    domain: Optional[str]
    subdomain: Optional[str]
    database_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    config: Dict[str, Any]


class TenantAdminService:
    """
    Service per operazioni amministrative sui tenant.
    Implementa logica business per gestione tenant.
    """
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
    
    async def create_tenant(self, tenant_data: TenantCreate) -> Dict[str, Any]:
        """
        Crea nuovo tenant con tutte le risorse necessarie.
        
        Steps:
        1. Valida dati tenant
        2. Crea database dedicato (opzionale)
        3. Esegue migrations
        4. Crea user admin tenant
        5. Inizializza configurazione
        """
        logger.info(f"Creating tenant: {tenant_data.name}")
        
        # TODO: Implementare con tuo DB
        # 1. Crea record tenant
        tenant_id = self._generate_tenant_id(tenant_data.name)
        
        # 2. Crea database se necessario
        if tenant_data.database_name or self.db_pool:
            await self._create_tenant_database(tenant_id, tenant_data)
        
        # 3. Esegui migrations
        await self._run_tenant_migrations(tenant_id)
        
        # 4. Inizializza dati default
        await self._initialize_tenant_data(tenant_id, tenant_data)
        
        logger.info(f"Tenant created successfully: {tenant_id}")
        
        return {
            "id": tenant_id,
            "name": tenant_data.name,
            "domain": tenant_data.domain,
            "subdomain": tenant_data.subdomain,
            "database_name": tenant_data.database_name or f"tenant_{tenant_id}",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "config": tenant_data.config
        }
    
    async def delete_tenant(self, tenant_id: str, force: bool = False):
        """
        Elimina tenant e tutte le sue risorse.
        
        Args:
            tenant_id: ID tenant da eliminare
            force: Se True, elimina anche se ci sono dati
        """
        logger.warning(f"Deleting tenant: {tenant_id} (force={force})")
        
        # 1. Verifica se tenant ha dati attivi
        if not force:
            has_active_data = await self._check_active_data(tenant_id)
            if has_active_data:
                raise ValueError(
                    "Tenant has active data. Use force=True to delete anyway"
                )
        
        # 2. Backup dati (opzionale)
        if not force:
            await self._backup_tenant_data(tenant_id)
        
        # 3. Elimina database
        await self._drop_tenant_database(tenant_id)
        
        # 4. Chiudi connessioni pool
        if self.db_pool:
            await self.db_pool.close_tenant_pool(tenant_id)
        
        # 5. Elimina record tenant
        # TODO: Implementare con tuo DB
        
        logger.info(f"Tenant deleted: {tenant_id}")
    
    async def update_tenant(
        self, 
        tenant_id: str, 
        update_data: TenantUpdate
    ) -> Dict[str, Any]:
        """Aggiorna configurazione tenant"""
        logger.info(f"Updating tenant: {tenant_id}")
        
        # TODO: Implementare con tuo DB
        # Update solo campi forniti
        updates = update_data.model_dump(exclude_unset=True)
        
        return {
            "id": tenant_id,
            "updated_at": datetime.utcnow(),
            **updates
        }
    
    async def list_tenants(
        self, 
        skip: int = 0, 
        limit: int = 100,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Lista tutti i tenant"""
        # TODO: Implementare con tuo DB
        return []
    
    async def get_tenant(self, tenant_id: str) -> Dict[str, Any]:
        """Ottiene dettagli tenant specifico"""
        # TODO: Implementare con tuo DB
        return {}
    
    # Helper methods
    def _generate_tenant_id(self, name: str) -> str:
        """Genera ID univoco per tenant"""
        import uuid
        import re
        
        # Slugify manuale (no dependencies extra)
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        unique = str(uuid.uuid4())[:8]
        return f"{slug}-{unique}"
    
    async def _create_tenant_database(self, tenant_id: str, tenant_data: TenantCreate):
        """Crea database dedicato per tenant"""
        # TODO: Implementare creazione DB
        pass
    
    async def _run_tenant_migrations(self, tenant_id: str):
        """Esegue migrations sul database tenant"""
        # TODO: Implementare migrations (Alembic?)
        pass
    
    async def _initialize_tenant_data(self, tenant_id: str, tenant_data: TenantCreate):
        """Inizializza dati default per nuovo tenant"""
        # TODO: Crea admin user, config default, etc.
        pass
    
    async def _check_active_data(self, tenant_id: str) -> bool:
        """Verifica se tenant ha dati attivi"""
        # TODO: Check users, records, etc.
        return False
    
    async def _backup_tenant_data(self, tenant_id: str):
        """Backup dati tenant prima di eliminazione"""
        # TODO: Export dati
        pass
    
    async def _drop_tenant_database(self, tenant_id: str):
        """Elimina database tenant"""
        # TODO: DROP database
        pass


# Router Admin API
def create_admin_router(
    admin_service: TenantAdminService,
    require_admin_auth  # Tua dependency per autenticazione admin
) -> APIRouter:
    """
    Crea router con API admin per gestione tenant.
    IMPORTANTE: Proteggere con autenticazione admin!
    """
    
    router = APIRouter(
        prefix="/admin/tenants",
        tags=["admin", "tenants"],
        dependencies=[Depends(require_admin_auth)]
    )
    
    @router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
    async def create_tenant(tenant_data: TenantCreate):
        """Crea nuovo tenant con risorse dedicate"""
        try:
            tenant = await admin_service.create_tenant(tenant_data)
            return tenant
        except Exception as e:
            logger.error(f"Failed to create tenant: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create tenant: {str(e)}"
            )
    
    @router.get("/", response_model=List[TenantResponse])
    async def list_tenants(
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True
    ):
        """Lista tutti i tenant"""
        return await admin_service.list_tenants(skip, limit, active_only)
    
    @router.get("/{tenant_id}", response_model=TenantResponse)
    async def get_tenant(tenant_id: str):
        """Ottiene dettagli tenant specifico"""
        tenant = await admin_service.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {tenant_id} not found"
            )
        return tenant
    
    @router.patch("/{tenant_id}", response_model=TenantResponse)
    async def update_tenant(tenant_id: str, update_data: TenantUpdate):
        """Aggiorna configurazione tenant"""
        try:
            return await admin_service.update_tenant(tenant_id, update_data)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
    
    @router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_tenant(tenant_id: str, force: bool = False):
        """
        Elimina tenant e tutte le sue risorse.
        ATTENZIONE: Operazione irreversibile!
        """
        try:
            await admin_service.delete_tenant(tenant_id, force)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    
    return router


# Esempio di utilizzo
"""
from linkbay_multitenant.admin import TenantAdminService, create_admin_router

# Setup service
admin_service = TenantAdminService(db_pool=db_pool)

# Dependency per autenticazione admin
async def require_admin_auth(token: str = Header(...)):
    # Verifica token admin
    if not is_admin(token):
        raise HTTPException(401, "Admin access required")

# Crea e registra router
admin_router = create_admin_router(admin_service, require_admin_auth)
app.include_router(admin_router)

# API disponibili:
# POST   /admin/tenants          - Crea tenant
# GET    /admin/tenants          - Lista tenant
# GET    /admin/tenants/{id}     - Dettagli tenant
# PATCH  /admin/tenants/{id}     - Aggiorna tenant
# DELETE /admin/tenants/{id}     - Elimina tenant
"""
