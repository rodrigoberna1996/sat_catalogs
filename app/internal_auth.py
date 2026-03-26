"""Autenticacion interna via clave compartida X-Internal-Key."""
import os

from fastapi import Header, HTTPException


async def require_internal_key(x_internal_key: str = Header(..., alias="x-internal-key")) -> None:
    """Verifica que la solicitud incluya la X-Internal-Key correcta."""
    internal_api_key = os.getenv("INTERNAL_API_KEY", "")
    if not internal_api_key or x_internal_key != internal_api_key:
        raise HTTPException(status_code=403, detail="Acceso no autorizado.")
