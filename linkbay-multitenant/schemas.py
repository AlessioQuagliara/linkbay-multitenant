from pydantic import BaseModel
from typing import Optional, Dict, Any, Protocol
from enum import Enum

class TenantStrategy(str, Enum):
    SUBDOMAIN = "subdomain"
    HEADER = "header" 
    PATH = "path"
    JWT = "jwt"

class DatabaseConfig(BaseModel):
    database_url: str
    pool_size: int = 5
    max_overflow: int = 10

class TenantInfo(BaseModel):
    id: str
    name: str
    domain: Optional[str] = None
    database_config: Optional[DatabaseConfig] = None
    metadata: Dict[str, Any] = {}

class TenantServiceProtocol(Protocol):
    async def get_tenant_by_id(self, tenant_id: str) -> Optional[TenantInfo]: ...
    async def get_tenant_by_domain(self, domain: str) -> Optional[TenantInfo]: ...
    async def get_tenant_database_config(self, tenant_id: str) -> Optional[DatabaseConfig]: ...
    async def get_all_tenants(self) -> list[TenantInfo]: ...