import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from ..auth import (
    create_access_token,
    ensure_bootstrap_admin,
    hash_password,
    normalize_email,
    require_user,
    users_container,
    verify_password,
)
from ..azure_clients import AzureClients, get_azure_clients
from ..config import Settings, get_settings
from ..dependencies import require_services
from ..models import AuthResponse, LoginRequest, RegisterRequest, UserProfile

router = APIRouter(prefix="/auth", tags=["authentication"])


def profile(user: dict) -> UserProfile:
    return UserProfile(
        id=user["id"],
        email=user["email"],
        display_name=user.get("displayName") or user["email"],
        role=user.get("role", "user"),
    )


async def find_user(login: str, settings: Settings, clients: AzureClients) -> dict | None:
    query = "SELECT TOP 1 * FROM c WHERE c.email = @login OR c.username = @login"
    async for item in users_container(settings, clients).query_items(
        query=query,
        parameters=[{"name": "@login", "value": normalize_email(login)}],
    ):
        return item
    return None


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    dependencies=[Depends(require_services("azureCosmosDB", "applicationAuthentication"))],
)
async def register(
    body: RegisterRequest,
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> AuthResponse:
    email = normalize_email(str(body.email))
    if email == normalize_email(settings.bootstrap_admin_email):
        raise HTTPException(409, "This email is reserved for the administrator.")
    if await find_user(email, settings, clients):
        raise HTTPException(409, "An account with this email already exists.")
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "username": email,
        "displayName": body.display_name.strip(),
        "passwordHash": hash_password(body.password),
        "role": "user",
        "createdAt": datetime.now(UTC).isoformat(),
    }
    await users_container(settings, clients).create_item(user)
    return AuthResponse(
        access_token=create_access_token(user, settings),
        user=profile(user),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(require_services("azureCosmosDB", "applicationAuthentication"))],
)
async def login(
    body: LoginRequest,
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> AuthResponse:
    login_value = normalize_email(body.email)
    if login_value == settings.bootstrap_admin_username.lower():
        user = await ensure_bootstrap_admin(settings, clients)
    else:
        user = await find_user(login_value, settings, clients)
    if not user or not verify_password(body.password, user["passwordHash"]):
        raise HTTPException(401, "Incorrect email/username or password.")
    return AuthResponse(
        access_token=create_access_token(user, settings),
        user=profile(user),
    )


@router.get("/me", response_model=UserProfile)
async def me(claims: dict = Depends(require_user)) -> UserProfile:
    return UserProfile(
        id=claims["sub"],
        email=claims["email"],
        display_name=claims.get("name") or claims["email"],
        role=claims.get("role", "user"),
    )
