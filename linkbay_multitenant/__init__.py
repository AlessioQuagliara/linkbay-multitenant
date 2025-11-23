from .core import MultitenantCore, TenantManager
from .dependencies import get_tenant, get_tenant_db, require_tenant
from .middleware import MultitenantMiddleware
from .router import MultitenantRouter
from .schemas import TenantInfo, DatabaseConfig

# Enterprise features
from .db_pool import TenantDBPool
from .security import TenantQueryInterceptor, TenantSecurityException, TenantQueryBuilder, AdminQueryContext
from .context import TenantContext, TenantContextManager, run_with_tenant_context, require_tenant_context
from .admin import TenantAdminService, create_admin_router, TenantCreate, TenantUpdate, TenantResponse
from .cache import TenantCache, TenantCacheService, cache_cleanup_task
from .metrics import TenantMetrics, MetricsCollector, MetricsMiddleware
from .migration import TenantMigrationService, MigrationJob, MigrationStatus, create_migration_router

__version__ = "1.0.0-beta"
__all__ = [
    # Core
    "MultitenantCore",
    "TenantManager", 
    "get_tenant",
    "get_tenant_db",
    "require_tenant",
    "MultitenantMiddleware",
    "MultitenantRouter",
    "TenantInfo",
    "DatabaseConfig",
    
    # Enterprise - DB Pool
    "TenantDBPool",
    
    # Enterprise - Security
    "TenantQueryInterceptor",
    "TenantSecurityException",
    "TenantQueryBuilder",
    "AdminQueryContext",
    
    # Enterprise - Context
    "TenantContext",
    "TenantContextManager",
    "run_with_tenant_context",
    "require_tenant_context",
    
    # Enterprise - Admin
    "TenantAdminService",
    "create_admin_router",
    "TenantCreate",
    "TenantUpdate",
    "TenantResponse",
    
    # Enterprise - Cache
    "TenantCache",
    "TenantCacheService",
    "cache_cleanup_task",
    
    # Enterprise - Metrics
    "TenantMetrics",
    "MetricsCollector",
    "MetricsMiddleware",
    
    # Enterprise - Migration
    "TenantMigrationService",
    "MigrationJob",
    "MigrationStatus",
    "create_migration_router",
]