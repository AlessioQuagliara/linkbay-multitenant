"""
Query interceptor per sicurezza multitenant.
Previene data leak tra tenant verificando filtri obbligatori.
"""
from typing import Optional, Set, Any
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine
import logging

logger = logging.getLogger(__name__)


class TenantSecurityException(Exception):
    """Eccezione per violazioni di sicurezza tenant"""
    pass


class TenantQueryInterceptor:
    """
    Interceptor che verifica che tutte le query includano filtri tenant.
    Previene accidentali data leak cross-tenant.
    """
    
    def __init__(
        self,
        tenant_column_name: str = "tenant_id",
        strict_mode: bool = True,
        exempt_tables: Optional[Set[str]] = None
    ):
        """
        Args:
            tenant_column_name: Nome colonna tenant nei modelli
            strict_mode: Se True, blocca query senza filtro tenant
            exempt_tables: Set di tabelle esenti dal controllo (es. config globali)
        """
        self.tenant_column_name = tenant_column_name
        self.strict_mode = strict_mode
        self.exempt_tables = exempt_tables or set()
        self._enabled = True
        
        logger.info(f"TenantQueryInterceptor initialized (strict={strict_mode})")
    
    def disable(self):
        """Disabilita temporaneamente i controlli (es. per admin operations)"""
        self._enabled = False
    
    def enable(self):
        """Riabilita i controlli"""
        self._enabled = True
    
    def is_exempt_table(self, table_name: str) -> bool:
        """Verifica se tabella è esente dai controlli"""
        return table_name in self.exempt_tables
    
    def has_tenant_filter(self, query_text: str, table_names: Set[str]) -> bool:
        """
        Verifica se query contiene filtro tenant.
        Analizza il testo SQL per trovare WHERE tenant_id = ...
        """
        # Skip se tutte le tabelle sono esenti
        if all(self.is_exempt_table(t) for t in table_names):
            return True
        
        query_lower = query_text.lower()
        
        # Verifica presenza filtro tenant
        has_filter = (
            f"{self.tenant_column_name}" in query_lower and
            "where" in query_lower
        )
        
        return has_filter
    
    def before_execute(self, conn, clauseelement, multiparams, params, execution_options):
        """
        Hook chiamato prima di ogni query.
        Verifica presenza filtro tenant.
        """
        if not self._enabled:
            return
        
        # Converti query in stringa SQL
        query_text = str(clauseelement)
        
        # Estrai nomi tabelle (parsing semplificato)
        table_names = self._extract_table_names(query_text)
        
        # Verifica filtro tenant
        if not self.has_tenant_filter(query_text, table_names):
            error_msg = (
                f"SECURITY VIOLATION: Query senza filtro tenant!\n"
                f"Tables: {table_names}\n"
                f"Query: {query_text[:200]}..."
            )
            
            logger.error(error_msg)
            
            if self.strict_mode:
                raise TenantSecurityException(error_msg)
            else:
                logger.warning("Strict mode OFF - query consentita ma non sicura")
    
    def _extract_table_names(self, query_text: str) -> Set[str]:
        """
        Estrae nomi tabelle dalla query SQL.
        Parsing semplificato - può essere esteso.
        """
        import re
        
        # Pattern per trovare FROM table, JOIN table, etc.
        patterns = [
            r"FROM\s+(\w+)",
            r"JOIN\s+(\w+)",
            r"UPDATE\s+(\w+)",
            r"INSERT\s+INTO\s+(\w+)",
            r"DELETE\s+FROM\s+(\w+)"
        ]
        
        tables = set()
        query_upper = query_text.upper()
        
        for pattern in patterns:
            matches = re.finditer(pattern, query_upper)
            for match in matches:
                tables.add(match.group(1).lower())
        
        return tables
    
    def register_with_engine(self, engine: Engine):
        """Registra interceptor con SQLAlchemy engine"""
        event.listen(
            engine,
            "before_cursor_execute",
            self.before_execute
        )
        logger.info(f"Interceptor registered with engine")
    
    def register_with_async_engine(self, engine: AsyncEngine):
        """Registra interceptor con async engine"""
        sync_engine = engine.sync_engine
        self.register_with_engine(sync_engine)


class TenantQueryBuilder:
    """
    Helper per costruire query sicure con filtro tenant automatico.
    Uso consigliato invece di query raw.
    """
    
    def __init__(self, tenant_id: str, tenant_column: str = "tenant_id"):
        self.tenant_id = tenant_id
        self.tenant_column = tenant_column
    
    def filter_query(self, query):
        """Applica automaticamente filtro tenant a query SQLAlchemy"""
        return query.filter_by(**{self.tenant_column: self.tenant_id})
    
    def filter_model(self, model, session):
        """Query base filtrata per tenant"""
        return session.query(model).filter(
            getattr(model, self.tenant_column) == self.tenant_id
        )


# Context manager per operazioni admin senza filtri
class AdminQueryContext:
    """
    Context manager per eseguire query admin senza filtri tenant.
    Usare con cautela e solo per operazioni amministrative.
    """
    
    def __init__(self, interceptor: TenantQueryInterceptor):
        self.interceptor = interceptor
        self.was_enabled = True
    
    def __enter__(self):
        self.was_enabled = self.interceptor._enabled
        self.interceptor.disable()
        logger.warning("Admin context: tenant filters DISABLED")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.was_enabled:
            self.interceptor.enable()
        logger.info("Admin context: tenant filters restored")


# Esempio di utilizzo
"""
# Setup
interceptor = TenantQueryInterceptor(
    tenant_column_name="tenant_id",
    strict_mode=True,
    exempt_tables={"system_config", "migrations"}
)

# Registra con engine
interceptor.register_with_async_engine(engine)

# Query builder sicuro
@app.get("/products")
async def get_products(tenant = Depends(require_tenant), session = Depends(get_db)):
    builder = TenantQueryBuilder(tenant.id)
    query = session.query(Product)
    query = builder.filter_query(query)
    return query.all()

# Operazione admin (disabilita temporaneamente controlli)
with AdminQueryContext(interceptor):
    all_tenants = session.query(Tenant).all()
"""
