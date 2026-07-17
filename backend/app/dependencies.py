"""
Kio Shared Dependencies
FastAPI dependency injection for auth, tenancy, and roles.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import decode_token
from database.models import User
from database.session import get_db

# -------------------------------------------------------------------
# Security scheme
# -------------------------------------------------------------------
security = HTTPBearer()


# -------------------------------------------------------------------
# Get Current User
# -------------------------------------------------------------------
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Extract and validate JWT from Authorization header,
    then look up the user in the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(credentials.credentials)
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if user_id_str is None:
            raise credentials_exception
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type. Use access token.",
            )

        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


# -------------------------------------------------------------------
# Get Current Tenant
# -------------------------------------------------------------------
async def get_current_tenant(
    current_user: Annotated[User, Depends(get_current_user)],
) -> uuid.UUID:
    """Extract tenant_id from the authenticated user."""
    return current_user.tenant_id


# -------------------------------------------------------------------
# Role-Based Access Control
# -------------------------------------------------------------------
def require_role(*allowed_roles: str):
    """
    Factory that returns a dependency which checks the user's role.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
    """

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' does not have access to this resource",
            )
        return current_user

    return role_checker


# -------------------------------------------------------------------
# Convenience type aliases
# -------------------------------------------------------------------
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentTenant = Annotated[uuid.UUID, Depends(get_current_tenant)]
