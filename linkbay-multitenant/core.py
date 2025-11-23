from typing import Optional, Dict, Any
from .schemas import TenantInfo, TenantServiceProtocol, DatabaseConfig

class TenantManager:
    def __init__(self, tenant_service: TenantServiceProtocol):
        self.tenant_service = tenant_service
        self.tenant_cache: Dict[str, TenantInfo] = {}
    
    async def get_tenant(self, tenant_id: str) -> Optional[TenantInfo]:
        # Cache per performance
        if tenant_id in self.tenant_cache:
            return self.tenant_cache[tenant_id]
        
        tenant = await self.tenant_service.get_tenant_by_id(tenant_id)
        if tenant:
            self.tenant_cache[tenant_id] = tenant
        
        return tenant
    
    async def get_tenant_by_domain(self, domain: str) -> Optional[TenantInfo]:
        return await self.tenant_service.get_tenant_by_domain(domain)

class MultitenantCore:
    def __init__(
        self,
        tenant_service: TenantServiceProtocol,
        strategy: str = "header",
        tenant_header: str = "X-Tenant-ID",
        default_tenant: Optional[str] = None
    ):
        self.tenant_manager = TenantManager(tenant_service)
        self.strategy = strategy
        self.tenant_header = tenant_header
        self.default_tenant = default_tenant
    
    async def identify_tenant(self, request) -> Optional[str]:
        """Identifica il tenant dalla richiesta"""
        if self.strategy == "header":
            return request.headers.get(self.tenant_header)
        
        elif self.strategy == "subdomain":
            host = request.headers.get("host", "")
            subdomain = host.split(".")[0]
            return subdomain if subdomain != "www" else None
        
        elif self.strategy == "path":
            # /tenant-id/path/to/resource
            path_parts = request.url.path.split("/")
            return path_parts[1] if len(path_parts) > 1 else None
        
        return self.default_tenant
    
    async def get_tenant_info(self, request) -> Optional[TenantInfo]:
        tenant_id = await self.identify_tenant(request)
        if not tenant_id:
            return None
        
        return await self.tenant_manager.get_tenant(tenant_id)