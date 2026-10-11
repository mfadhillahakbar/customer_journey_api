import secrets
from fastapi import Depends, Security
from fastapi.security.api_key import APIKeyHeader
from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedException

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Validate X-API-Key header against configured application secret.
    Raises UnauthorizedException (401) on missing or invalid key.
    """
    if not api_key:
        raise UnauthorizedException("Header X-API-Key wajib disertakan.")

    # Secure constant-time comparison to prevent timing attacks
    is_valid = secrets.compare_digest(api_key, settings.API_KEY)
    if not is_valid:
        raise UnauthorizedException("Nilai X-API-Key tidak valid.")

    return api_key
