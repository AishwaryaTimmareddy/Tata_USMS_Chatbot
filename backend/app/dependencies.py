from fastapi import Depends, HTTPException, status

from .config import get_settings


def require_services(*names: str):
    async def dependency(settings=Depends(get_settings)) -> None:
        readiness = settings.readiness()
        missing = {name: readiness.get(name, []) for name in names if readiness.get(name)}
        if missing:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": "Azure services are not configured.", "missing": missing},
            )

    return dependency
