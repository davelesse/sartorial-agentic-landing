"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Security
Password hashing (bcrypt) + JWT tokens.
═══════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─────────────────────────────────────
# PASSWORDS
# ─────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─────────────────────────────────────
# JWT
# ─────────────────────────────────────

def create_access_token(
    user_id: UUID,
    tenant_id: UUID | None = None,
    role: str = "client",
) -> tuple[str, int]:
    """
    Create a JWT access token.
    Returns (token, expires_in_seconds).
    """
    expires_delta = timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id) if tenant_id else None,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict:
    """
    Decode & validate a JWT token.
    Raises JWTError if invalid/expired.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
