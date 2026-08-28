import os
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select

from backend.app.core.database import get_db
from backend.app.models import TokenRevocation, User

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Fail-closed boot validation (EM-1): a served app must never run on a
# forgeable signing key. Known defaults and short keys are rejected at
# startup by validate_secret_key(), which main.py lifespan enforces.
INSECURE_SECRET_KEYS = frozenset({
    "",
    "your-secret-key-change-in-production",
    "dev-secret-change-in-production",
    "secret",
    "changeme",
    "change-me",
    "supersecret",
})
MIN_SECRET_KEY_LENGTH = 32


def validate_secret_key(secret: Optional[str] = None) -> str:
    """Return the signing key if it is safe, else raise RuntimeError.

    Called from the app lifespan so the API refuses to boot (fail closed)
    when SECRET_KEY is missing, a known-insecure default, or too short.
    Passing an explicit `secret` validates that value instead of the
    module-level SECRET_KEY (used by tests).
    """
    value = SECRET_KEY if secret is None else secret
    if not value:
        raise RuntimeError(
            "SECRET_KEY is not set. Refusing to boot: JWT signatures would be "
            "forgeable. Export a strong random SECRET_KEY (>= 32 chars)."
        )
    if value in INSECURE_SECRET_KEYS:
        raise RuntimeError(
            "SECRET_KEY is a known-insecure default. Refusing to boot: anyone "
            "could forge valid JWTs. Export a strong random SECRET_KEY."
        )
    if len(value) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY is too short ({len(value)} chars < {MIN_SECRET_KEY_LENGTH}). "
            "Refusing to boot: short HMAC keys are brute-forceable."
        )
    return value


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _bcrypt_secret(password: str) -> bytes:
    # bcrypt's algorithm caps secrets at 72 bytes; passlib used to truncate
    # silently, bcrypt>=4.1 raises. Keep the truncation explicit.
    return password.encode("utf-8")[:72]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_bcrypt_secret(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_secret(password), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    revoked = await db.execute(
        select(TokenRevocation.token_hash).where(TokenRevocation.token_hash == token_hash)
    )
    if revoked.scalar_one_or_none() is not None:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    if payload.get("ver", 0) != user.auth_version:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_owner_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """The sole supported administrative authority is the configured owner."""
    owner_email = os.getenv("OWNER_EMAIL", "").strip().lower()
    if not owner_email or current_user.email.lower() != owner_email or not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required")
    return current_user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """Authenticate with either a username or an email address.

    OAuth2 calls the form field ``username`` even when an application accepts
    an email identifier. Keep that wire format while supporting both values.
    Email matching is case-insensitive; username matching retains the existing
    case-sensitive behavior.
    """
    identifier = username.strip()
    result = await db.execute(
        select(User).where(
            or_(
                User.username == identifier,
                func.lower(User.email) == identifier.lower(),
            )
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
