"""Autenticacion interna via clave compartida X-Internal-Key."""
import os

from fastapi import Header, HTTPException

_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


async def require_internal_key(x_internal_key: str = Header(..., alias="x-internal-key")) -> None:
    """Verifica que la solicitud incluya la X-Internal-Key correcta."""
    if not _INTERNAL_API_KEY or x_internal_key != _INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Acceso no autorizado.")
