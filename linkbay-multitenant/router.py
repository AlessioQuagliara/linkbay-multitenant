from fastapi import APIRouter, Depends
from typing import Optional, Callable, Any
from .dependencies import get_tenant, require_tenant

class MultitenantRouter:
    def __init__(self, prefix: str = "", tags: Optional[list] = None):
        self.router = APIRouter(prefix=prefix, tags=tags)
        self.tenant_dependency = get_tenant
    
    def add_route(self, path: str, method: str, endpoint: Callable, **kwargs):
        """Aggiunge una route con dipendenza tenant"""
        # Aggiungi automaticamente la dipendenza tenant se non specificata
        if "dependencies" not in kwargs:
            kwargs["dependencies"] = [Depends(self.tenant_dependency)]
        
        self.router.add_route(path, method, endpoint, **kwargs)
    
    def get(self, path: str, **kwargs):
        def decorator(func):
            self.add_route(path, "GET", func, **kwargs)
            return func
        return decorator
    
    def post(self, path: str, **kwargs):
        def decorator(func):
            self.add_route(path, "POST", func, **kwargs)
            return func
        return decorator
    
    def put(self, path: str, **kwargs):
        def decorator(func):
            self.add_route(path, "PUT", func, **kwargs)
            return func
        return decorator
    
    def delete(self, path: str, **kwargs):
        def decorator(func):
            self.add_route(path, "DELETE", func, **kwargs)
            return func
        return decorator
    
    def include_router(self, router: APIRouter):
        """Includi un router esistente"""
        self.router.include_router(router)