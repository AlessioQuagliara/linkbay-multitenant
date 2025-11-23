import re
from typing import Optional
from .schemas import TenantInfo

def validate_tenant_id(tenant_id: str) -> bool:
    """Valida che l'ID tenant sia alfanumerico e sicuro"""
    if not tenant_id or len(tenant_id) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', tenant_id))

def extract_subdomain(host: str) -> Optional[str]:
    """Estrae il subdomain dall'host"""
    parts = host.split(".")
    if len(parts) > 2:
        subdomain = parts[0]
        return subdomain if subdomain not in ["www", "app"] else None
    return None

def create_tenant_database_name(tenant_id: str, base_name: str = "app") -> str:
    """Crea un nome database sicuro per il tenant"""
    safe_id = re.sub(r'[^a-zA-Z0-9]', '_', tenant_id)
    return f"{base_name}_{safe_id}"

def generate_tenant_api_key(tenant_id: str) -> str:
    """Genera una API key per il tenant"""
    import secrets
    import hashlib
    random_part = secrets.token_urlsafe(16)
    combined = f"{tenant_id}:{random_part}"
    return hashlib.sha256(combined.encode()).hexdigest()[:32]