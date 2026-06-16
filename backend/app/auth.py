from datetime import UTC, datetime, timedelta

import jwt
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from .azure_clients import AzureClients, get_azure_clients
from .config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)
password_hash = PasswordHash.recommended()


def normalize_email(value: str) -> str:
    return value.strip().lower()


def hash_password(value: str) -> str:
    return password_hash.hash(value)


def verify_password(value: str, encoded: str) -> bool:
    return password_hash.verify(value, encoded)


def create_access_token(user: dict, settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user["id"],
            "email": user["email"],
            "name": user.get("displayName") or user["email"],
            "role": user.get("role", "user"),
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_access_token_minutes),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings=Depends(get_settings),
) -> dict:
    if not settings.jwt_secret_key:
        raise HTTPException(503, "JWT_SECRET_KEY is not configured.")
    if not credentials:
        raise HTTPException(401, "Sign-in is required.")
    try:
        return jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "The access token is invalid or expired.") from exc


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings=Depends(get_settings),
) -> dict | None:
    if not credentials:
        return None
    return await require_user(credentials, settings)


async def require_admin(claims: dict = Depends(require_user)) -> dict:
    if claims.get("role") != "admin":
        raise HTTPException(403, "Administrator permission is required.")
    return claims


def user_id(claims: dict) -> str:
    return claims["sub"]


def users_container(settings: Settings, clients: AzureClients):
    return clients.cosmos().get_database_client(
        settings.azure_cosmos_database
    ).get_container_client(settings.azure_cosmos_users_container)


async def ensure_bootstrap_admin(
    settings: Settings,
    clients: AzureClients,
) -> dict:
    """Create the requested initial admin when the users container is available."""
    if not settings.jwt_secret_key:
        raise HTTPException(503, "JWT_SECRET_KEY is not configured.")
    container = users_container(settings, clients)
    admin_id = f"admin:{settings.bootstrap_admin_username.lower()}"
    try:
        return await container.read_item(item=admin_id, partition_key=admin_id)
    except CosmosResourceNotFoundError:
        user = {
            "id": admin_id,
            "email": normalize_email(settings.bootstrap_admin_email),
            "username": settings.bootstrap_admin_username.lower(),
            "displayName": "Saffron Administrator",
            "passwordHash": hash_password(settings.bootstrap_admin_password),
            "role": "admin",
            "createdAt": datetime.now(UTC).isoformat(),
        }
        await container.create_item(user)
        return user
