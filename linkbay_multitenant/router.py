from fastapi import APIRouter, Depends
from typing import Optional, Callable, Any, List
from .dependencies import get_tenant, require_tenant

class MultitenantRouter:
    def __init__(self, prefix: str = "", tags: Optional[list] = None):
        self.router = APIRouter(prefix=prefix, tags=tags)
        self.tenant_dependency = get_tenant
    
    def add_route(self, path: str, method: str, endpoint: Callable, **kwargs):
        """Aggiunge una route con dipendenza tenant usando add_api_route"""
        # Estrai dependencies se esistono
        dependencies = kwargs.pop("dependencies", None)
        
        # Aggiungi automaticamente la dipendenza tenant se non specificata
        if dependencies is None:
            dependencies = [Depends(self.tenant_dependency)]
        
        # Usa add_api_route invece di add_route per supportare dependencies
        methods = [method] if isinstance(method, str) else method
        self.router.add_api_route(
            path, 
            endpoint, 
            methods=methods,
            dependencies=dependencies,
            **kwargs
        )
    
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