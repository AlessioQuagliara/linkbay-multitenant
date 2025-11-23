"""
Pool di connessioni database per tenant multipli.
Gestisce connessioni separate per ogni tenant con configurazione ottimizzata.
"""
from typing import Dict, Optional, Callable
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)


class TenantDBPool:
    """
    Pool di connessioni database per architettura multitenant.
    Ogni tenant può avere il proprio database con connessioni ottimizzate.
    """
    
    def __init__(
        self,
        get_tenant_db_url: Callable[[str], str],
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        echo: bool = False
    ):
        """
        Args:
            get_tenant_db_url: Funzione che ritorna DB URL dato tenant_id
            pool_size: Numero di connessioni permanenti per tenant
            max_overflow: Connessioni aggiuntive temporanee
            pool_timeout: Timeout in secondi per ottenere connessione
            pool_recycle: Secondi dopo cui riciclare connessione
            echo: Log SQL queries (debug)
        """
        self.get_tenant_db_url = get_tenant_db_url
        self.pools: Dict[str, AsyncEngine] = {}
        self.sessions: Dict[str, sessionmaker] = {}
        
        self.pool_config = {
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_timeout": pool_timeout,
            "pool_recycle": pool_recycle,
            "echo": echo,
            "pool_pre_ping": True,  # Verifica connessioni prima dell'uso
        }
        
        logger.info(f"TenantDBPool initialized with config: {self.pool_config}")
    
    async def get_engine(self, tenant_id: str) -> AsyncEngine:
        """
        Ottiene o crea engine per tenant specifico.
        Thread-safe e ottimizzato per async.
        """
        if tenant_id not in self.pools:
            logger.info(f"Creating new DB pool for tenant: {tenant_id}")
            
            db_url = self.get_tenant_db_url(tenant_id)
            
            engine = create_async_engine(
                db_url,
                **self.pool_config
            )
            
            self.pools[tenant_id] = engine
            
            # Crea sessionmaker per questo tenant
            self.sessions[tenant_id] = sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info(f"DB pool created successfully for tenant: {tenant_id}")
        
        return self.pools[tenant_id]
    
    async def get_session(self, tenant_id: str) -> AsyncSession:
        """
        Ottiene una sessione DB per il tenant.
        Usa questo per query sicure isolate per tenant.
        """
        if tenant_id not in self.sessions:
            await self.get_engine(tenant_id)
        
        session_factory = self.sessions[tenant_id]
        return session_factory()
    
    async def close_tenant_pool(self, tenant_id: str):
        """Chiude e rimuove pool per tenant specifico"""
        if tenant_id in self.pools:
            logger.info(f"Closing DB pool for tenant: {tenant_id}")
            await self.pools[tenant_id].dispose()
            del self.pools[tenant_id]
            del self.sessions[tenant_id]
    
    async def close_all(self):
        """Chiude tutti i pool di connessioni"""
        logger.info("Closing all tenant DB pools")
        for tenant_id in list(self.pools.keys()):
            await self.close_tenant_pool(tenant_id)
    
    def get_pool_stats(self, tenant_id: str) -> Optional[Dict]:
        """Statistiche del pool per monitoring"""
        if tenant_id not in self.pools:
            return None
        
        engine = self.pools[tenant_id]
        pool = engine.pool
        
        return {
            "tenant_id": tenant_id,
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total_connections": pool.size() + pool.overflow()
        }
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Statistiche di tutti i pool attivi"""
        return {
            tenant_id: self.get_pool_stats(tenant_id)
            for tenant_id in self.pools.keys()
        }


# Esempio di utilizzo
"""
# Setup
def get_tenant_db_url(tenant_id: str) -> str:
    return f"postgresql+asyncpg://user:pass@localhost/tenant_{tenant_id}"

db_pool = TenantDBPool(get_tenant_db_url)

# In una route
@app.get("/data")
async def get_data(tenant = Depends(require_tenant)):
    async with await db_pool.get_session(tenant.id) as session:
        result = await session.execute(select(Product))
        return result.scalars().all()

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown():
    await db_pool.close_all()
"""
