from dataclasses import dataclass

import aiohttp
from azure.core.exceptions import AzureError
from fastapi import HTTPException

from ..azure_clients import AzureClients
from ..config import Settings


@dataclass(frozen=True)
class SafetyResult:
    blocked: bool
    categories: list[str]


class ContentSafetyService:
    def __init__(self, settings: Settings, clients: AzureClients):
        self.settings = settings
        self.clients = clients

    async def analyze_text(self, text: str) -> SafetyResult:
        if not self.settings.azure_content_safety_endpoint:
            return SafetyResult(blocked=False, categories=[])

        try:
            token = await self.clients.identity.get_token(
                "https://cognitiveservices.azure.com/.default"
            )
        except AzureError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Azure Content Safety token request failed. Azure error: {exc}",
            ) from exc

        endpoint = self.settings.azure_content_safety_endpoint.rstrip("/")
        url = (
            f"{endpoint}/contentsafety/text:analyze"
            f"?api-version={self.settings.azure_content_safety_api_version}"
        )
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "categories": ["Hate", "Sexual", "SelfHarm", "Violence"],
            "outputType": "FourSeverityLevels",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                body = await response.json(content_type=None)
                if response.status >= 400:
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Azure Content Safety analysis failed. "
                            f"Azure status: {response.status}; response: {body}"
                        ),
                    )

        blocked_categories = [
            item.get("category", "unknown")
            for item in body.get("categoriesAnalysis", [])
            if int(item.get("severity", 0) or 0)
            >= self.settings.azure_content_safety_block_threshold
        ]
        return SafetyResult(
            blocked=bool(blocked_categories),
            categories=blocked_categories,
        )

    async def require_safe(self, text: str, label: str, status_code: int = 400) -> None:
        result = await self.analyze_text(text)
        if result.blocked:
            raise HTTPException(
                status_code=status_code,
                detail={
                    "message": f"{label} was blocked by Azure Content Safety.",
                    "categories": result.categories,
                },
            )
