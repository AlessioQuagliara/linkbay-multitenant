"""
Context management per tenant usando contextvars.
Preserva tenant context in async tasks e background jobs.
"""
from contextvars import ContextVar
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Context variables per tenant
current_tenant_id: ContextVar[Optional[str]] = ContextVar('current_tenant_id', default=None)
current_tenant_data: ContextVar[Optional[dict]] = ContextVar('current_tenant_data', default=None)


class TenantContext:
    """
    Gestisce il context tenant per async operations.
    Usa contextvars per preservare tenant in background tasks.
    """
    
    @staticmethod
    def set_tenant_id(tenant_id: str):
        """Imposta tenant_id nel context corrente"""
        current_tenant_id.set(tenant_id)
        logger.debug(f"Tenant context set: {tenant_id}")
    
    @staticmethod
    def get_tenant_id() -> Optional[str]:
        """Ottiene tenant_id dal context corrente"""
        return current_tenant_id.get()
    
    @staticmethod
    def set_tenant_data(tenant_data: dict):
        """Imposta dati completi tenant nel context"""
        current_tenant_data.set(tenant_data)
        if 'id' in tenant_data:
            current_tenant_id.set(tenant_data['id'])
    
    @staticmethod
    def get_tenant_data() -> Optional[dict]:
        """Ottiene dati tenant dal context"""
        return current_tenant_data.get()
    
    @staticmethod
    def clear():
        """Pulisce il context tenant"""
        current_tenant_id.set(None)
        current_tenant_data.set(None)
        logger.debug("Tenant context cleared")
    
    @staticmethod
    def require_tenant_id() -> str:
        """
        Ottiene tenant_id obbligatorio.
        Solleva eccezione se non presente.
        """
        tenant_id = current_tenant_id.get()
        if not tenant_id:
            raise ValueError("No tenant context available")
        return tenant_id


class TenantContextManager:
    """
    Context manager per gestire tenant scope.
    Usalo per garantire cleanup del context.
    """
    
    def __init__(self, tenant_id: str, tenant_data: Optional[dict] = None):
        self.tenant_id = tenant_id
        self.tenant_data = tenant_data
        self.previous_tenant_id = None
        self.previous_tenant_data = None
    
    def __enter__(self):
        # Salva context precedente
        self.previous_tenant_id = TenantContext.get_tenant_id()
        self.previous_tenant_data = TenantContext.get_tenant_data()
        
        # Imposta nuovo context
        TenantContext.set_tenant_id(self.tenant_id)
        if self.tenant_data:
            TenantContext.set_tenant_data(self.tenant_data)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Ripristina context precedente
        if self.previous_tenant_id:
            TenantContext.set_tenant_id(self.previous_tenant_id)
        if self.previous_tenant_data:
            TenantContext.set_tenant_data(self.previous_tenant_data)
        else:
            TenantContext.clear()


async def run_with_tenant_context(tenant_id: str, coro):
    """
    Esegue una coroutine con tenant context impostato.
    Utile per background tasks.
    """
    with TenantContextManager(tenant_id):
        return await coro


# Decorator per funzioni che richiedono tenant context
def require_tenant_context(func):
    """
    Decorator che verifica presenza tenant context.
    Solleva eccezione se context non disponibile.
    """
    async def wrapper(*args, **kwargs):
        tenant_id = TenantContext.get_tenant_id()
        if not tenant_id:
            raise ValueError(
                f"Function {func.__name__} requires tenant context but none found"
            )
        return await func(*args, **kwargs)
    
    return wrapper


# Esempio di utilizzo
"""
# 1. In una route FastAPI (context automatico via middleware)
@app.get("/data")
async def get_data():
    tenant_id = TenantContext.get_tenant_id()
    return {"tenant": tenant_id}

# 2. Background task con context preserved
import asyncio

async def send_email(to: str, subject: str):
    # Context tenant disponibile automaticamente
    tenant_id = TenantContext.require_tenant_id()
    logger.info(f"Sending email for tenant {tenant_id}")
    # ... email logic

@app.post("/send")
async def trigger_email(background_tasks: BackgroundTasks):
    tenant_id = TenantContext.get_tenant_id()
    
    # Il context viene preservato nel background task
    background_tasks.add_task(
        run_with_tenant_context,
        tenant_id,
        send_email("user@example.com", "Hello")
    )

# 3. Async task manuale
async def process_data():
    tenant_id = TenantContext.require_tenant_id()
    # ... processing logic

async def main():
    with TenantContextManager("tenant-123"):
        await process_data()  # ✅ Context disponibile

# 4. Funzione decorata
@require_tenant_context
async def protected_operation():
    tenant_id = TenantContext.get_tenant_id()
    # ... operation logic

# 5. Switch tra tenant
async def admin_operation():
    # Salva tenant corrente
    original_tenant = TenantContext.get_tenant_id()
    
    # Lavora su altro tenant
    with TenantContextManager("admin-tenant"):
        # Operazioni su admin-tenant
        pass
    
    # Auto-restored a original_tenant
"""
