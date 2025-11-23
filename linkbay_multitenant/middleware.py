from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from .core import MultitenantCore

class MultitenantMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, multitenant_core: MultitenantCore):
        super().__init__(app)
        self.multitenant_core = multitenant_core
    
    async def dispatch(self, request: Request, call_next):
        # Identifica il tenant
        tenant_info = await self.multitenant_core.get_tenant_info(request)
        
        if not tenant_info and not self.multitenant_core.default_tenant:
            raise HTTPException(
                status_code=400, 
                detail="Tenant non identificato"
            )
        
        # Aggiungi info tenant alla request state
        request.state.tenant = tenant_info
        request.state.tenant_id = tenant_info.id if tenant_info else self.multitenant_core.default_tenant
        
        response = await call_next(request)
        return response