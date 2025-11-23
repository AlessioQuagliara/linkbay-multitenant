"""
Sistema di migrazione dati tra tenant.
Supporta export, import, e trasferimento sicuro di dati.
"""
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class MigrationStatus:
    """Stati possibili per una migrazione"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MigrationJob:
    """
    Rappresenta un job di migrazione tra tenant.
    """
    
    def __init__(
        self,
        job_id: str,
        source_tenant_id: str,
        target_tenant_id: str,
        tables: Optional[List[str]] = None
    ):
        self.job_id = job_id
        self.source_tenant_id = source_tenant_id
        self.target_tenant_id = target_tenant_id
        self.tables = tables or []
        
        self.status = MigrationStatus.PENDING
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        
        self.total_records = 0
        self.migrated_records = 0
        self.failed_records = 0
        self.errors: List[str] = []
    
    def start(self):
        """Marca job come iniziato"""
        self.status = MigrationStatus.RUNNING
        self.started_at = datetime.utcnow()
    
    def complete(self):
        """Marca job come completato"""
        self.status = MigrationStatus.COMPLETED
        self.completed_at = datetime.utcnow()
    
    def fail(self, error: str):
        """Marca job come fallito"""
        self.status = MigrationStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.errors.append(error)
    
    def get_progress(self) -> float:
        """Percentuale completamento (0-100)"""
        if self.total_records == 0:
            return 0.0
        return (self.migrated_records / self.total_records) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Esporta job info come dict"""
        return {
            "job_id": self.job_id,
            "source_tenant_id": self.source_tenant_id,
            "target_tenant_id": self.target_tenant_id,
            "tables": self.tables,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_records": self.total_records,
            "migrated_records": self.migrated_records,
            "failed_records": self.failed_records,
            "progress_percent": round(self.get_progress(), 2),
            "errors": self.errors
        }


class TenantMigrationService:
    """
    Service per gestire migrazioni dati tra tenant.
    """
    
    def __init__(self, db_pool=None, export_path: str = "/tmp/tenant_exports"):
        self.db_pool = db_pool
        self.export_path = Path(export_path)
        self.export_path.mkdir(parents=True, exist_ok=True)
        
        # Job tracking
        self.jobs: Dict[str, MigrationJob] = {}
        self._lock = asyncio.Lock()
        
        logger.info(f"TenantMigrationService initialized: export_path={export_path}")
    
    async def export_tenant_data(
        self,
        tenant_id: str,
        tables: Optional[List[str]] = None
    ) -> str:
        """
        Esporta tutti i dati di un tenant in formato JSON.
        
        Returns:
            Path al file export
        """
        logger.info(f"Exporting data for tenant: {tenant_id}")
        
        export_file = self.export_path / f"{tenant_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        # TODO: Implementare con tuo DB
        # Per ogni tabella:
        # 1. Query tutti i record del tenant
        # 2. Serializza in JSON
        # 3. Scrivi su file
        
        export_data = {
            "tenant_id": tenant_id,
            "exported_at": datetime.utcnow().isoformat(),
            "tables": tables or [],
            "data": {}
        }
        
        # Esempio struttura
        # for table in tables:
        #     records = await self._fetch_table_data(tenant_id, table)
        #     export_data["data"][table] = records
        
        with open(export_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        logger.info(f"Export completed: {export_file}")
        return str(export_file)
    
    async def import_tenant_data(
        self,
        tenant_id: str,
        export_file: str
    ):
        """
        Importa dati da file export in tenant target.
        """
        logger.info(f"Importing data to tenant {tenant_id} from {export_file}")
        
        with open(export_file, 'r') as f:
            export_data = json.load(f)
        
        # TODO: Implementare con tuo DB
        # Per ogni tabella nel file:
        # 1. Leggi records
        # 2. Adatta tenant_id ai nuovi valori
        # 3. Insert batch nel DB target
        
        logger.info(f"Import completed for tenant: {tenant_id}")
    
    async def migrate_tenant_data(
        self,
        source_tenant_id: str,
        target_tenant_id: str,
        tables: Optional[List[str]] = None,
        copy_mode: bool = False
    ) -> str:
        """
        Migra dati da un tenant a un altro.
        
        Args:
            source_tenant_id: Tenant sorgente
            target_tenant_id: Tenant destinazione
            tables: Lista tabelle da migrare (None = tutte)
            copy_mode: Se True, copia (non sposta). Se False, elimina da source
            
        Returns:
            Job ID per tracking
        """
        # Crea job
        import uuid
        job_id = str(uuid.uuid4())
        job = MigrationJob(job_id, source_tenant_id, target_tenant_id, tables)
        
        async with self._lock:
            self.jobs[job_id] = job
        
        # Esegui migrazione in background
        asyncio.create_task(self._run_migration(job, copy_mode))
        
        logger.info(f"Migration job created: {job_id}")
        return job_id
    
    async def _run_migration(self, job: MigrationJob, copy_mode: bool):
        """Esegue migrazione in background"""
        try:
            job.start()
            
            # 1. Export da source
            export_file = await self.export_tenant_data(
                job.source_tenant_id,
                job.tables
            )
            
            # 2. Import in target
            await self.import_tenant_data(job.target_tenant_id, export_file)
            
            # 3. Se move mode, elimina da source
            if not copy_mode:
                await self._delete_source_data(job.source_tenant_id, job.tables)
            
            # 4. Cleanup export file
            Path(export_file).unlink()
            
            job.complete()
            logger.info(f"Migration job completed: {job.job_id}")
            
        except Exception as e:
            logger.error(f"Migration job failed: {job.job_id} - {e}")
            job.fail(str(e))
    
    async def _delete_source_data(self, tenant_id: str, tables: List[str]):
        """Elimina dati sorgente dopo migrazione"""
        # TODO: Implementare con tuo DB
        pass
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Ottiene stato di un job di migrazione"""
        job = self.jobs.get(job_id)
        return job.to_dict() if job else None
    
    async def list_jobs(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lista job di migrazione con filtri opzionali.
        """
        jobs = self.jobs.values()
        
        if tenant_id:
            jobs = [
                j for j in jobs
                if j.source_tenant_id == tenant_id or j.target_tenant_id == tenant_id
            ]
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        return [job.to_dict() for job in jobs]
    
    async def cancel_job(self, job_id: str):
        """Cancella job in esecuzione"""
        job = self.jobs.get(job_id)
        if job and job.status == MigrationStatus.RUNNING:
            job.status = MigrationStatus.CANCELLED
            logger.info(f"Migration job cancelled: {job_id}")


# Router API per migrazioni
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel


class MigrationRequest(BaseModel):
    """Request per avviare migrazione"""
    source_tenant_id: str
    target_tenant_id: str
    tables: Optional[List[str]] = None
    copy_mode: bool = False


def create_migration_router(
    migration_service: TenantMigrationService,
    require_admin_auth
) -> APIRouter:
    """Crea router API per migrazioni"""
    
    router = APIRouter(
        prefix="/admin/migrations",
        tags=["admin", "migrations"],
        dependencies=[Depends(require_admin_auth)]
    )
    
    @router.post("/", status_code=202)
    async def start_migration(request: MigrationRequest):
        """Avvia migrazione dati tra tenant"""
        job_id = await migration_service.migrate_tenant_data(
            request.source_tenant_id,
            request.target_tenant_id,
            request.tables,
            request.copy_mode
        )
        return {"job_id": job_id, "status": "accepted"}
    
    @router.get("/{job_id}")
    async def get_migration_status(job_id: str):
        """Stato migrazione"""
        status = await migration_service.get_job_status(job_id)
        if not status:
            raise HTTPException(404, "Migration job not found")
        return status
    
    @router.get("/")
    async def list_migrations(
        tenant_id: Optional[str] = None,
        status: Optional[str] = None
    ):
        """Lista migrazioni"""
        return await migration_service.list_jobs(tenant_id, status)
    
    @router.post("/export/{tenant_id}")
    async def export_tenant(tenant_id: str, tables: Optional[List[str]] = None):
        """Export dati tenant"""
        export_file = await migration_service.export_tenant_data(tenant_id, tables)
        return {"export_file": export_file}
    
    @router.post("/import/{tenant_id}")
    async def import_tenant(tenant_id: str, export_file: str):
        """Import dati in tenant"""
        await migration_service.import_tenant_data(tenant_id, export_file)
        return {"status": "completed"}
    
    @router.delete("/{job_id}")
    async def cancel_migration(job_id: str):
        """Cancella migrazione in corso"""
        await migration_service.cancel_job(job_id)
        return {"status": "cancelled"}
    
    return router


# Esempio di utilizzo
"""
from linkbay_multitenant.migration import TenantMigrationService, create_migration_router

# Setup service
migration_service = TenantMigrationService(
    db_pool=db_pool,
    export_path="/var/tenant_exports"
)

# Dependency per autenticazione admin
async def require_admin_auth():
    # Verifica auth
    pass

# Registra router
migration_router = create_migration_router(migration_service, require_admin_auth)
app.include_router(migration_router)

# Uso programmatico
# 1. Migra tutto da tenant A a B
job_id = await migration_service.migrate_tenant_data(
    "tenant-a",
    "tenant-b",
    copy_mode=False  # Sposta, non copia
)

# 2. Copia solo alcune tabelle
job_id = await migration_service.migrate_tenant_data(
    "tenant-a",
    "tenant-b",
    tables=["users", "products"],
    copy_mode=True
)

# 3. Export per backup
export_file = await migration_service.export_tenant_data("tenant-a")

# 4. Monitor progresso
status = await migration_service.get_job_status(job_id)
print(f"Progress: {status['progress_percent']}%")
"""
