from functools import lru_cache
import logging

import aiohttp
from azure.core.exceptions import AzureError
from azure.core.credentials import AzureKeyCredential
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexerClient
from azure.storage.blob.aio import BlobServiceClient
from openai import AsyncAzureOpenAI

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


class AzureClients:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.identity = DefaultAzureCredential()
        self._openai: AsyncAzureOpenAI | None = None
        self._search: SearchClient | None = None
        self._indexer: SearchIndexerClient | None = None
        self._blobs: BlobServiceClient | None = None
        self._cosmos: CosmosClient | None = None
        self._http: aiohttp.ClientSession | None = None

    def openai(self) -> AsyncAzureOpenAI:
        if self._openai is not None:
            return self._openai

        kwargs = {
            "azure_endpoint": self.settings.azure_openai_endpoint,
            "api_version": self.settings.azure_openai_api_version,
            "max_retries": 0,
            "timeout": 12.0,
        }
        if self.settings.azure_openai_api_key:
            kwargs["api_key"] = self.settings.azure_openai_api_key
        else:
            from azure.identity.aio import get_bearer_token_provider

            kwargs["azure_ad_token_provider"] = get_bearer_token_provider(
                self.identity, "https://cognitiveservices.azure.com/.default"
            )
        self._openai = AsyncAzureOpenAI(**kwargs)
        return self._openai

    def search_credential(self):
        if self.settings.azure_search_api_key:
            return AzureKeyCredential(self.settings.azure_search_api_key)
        return self.identity

    def search(self) -> SearchClient:
        if self._search is None:
            self._search = SearchClient(
                endpoint=self.settings.azure_search_endpoint,
                index_name=self.settings.azure_search_index_name,
                credential=self.search_credential(),
            )
        return self._search

    def indexer(self) -> SearchIndexerClient:
        if self._indexer is None:
            self._indexer = SearchIndexerClient(
                endpoint=self.settings.azure_search_endpoint,
                credential=self.search_credential(),
            )
        return self._indexer

    def blobs(self) -> BlobServiceClient:
        if self._blobs is not None:
            return self._blobs

        if self.settings.azure_storage_connection_string:
            self._blobs = BlobServiceClient.from_connection_string(
                self.settings.azure_storage_connection_string
            )
        else:
            self._blobs = BlobServiceClient(
                account_url=self.settings.azure_storage_account_url,
                credential=self.identity,
            )
        return self._blobs

    def cosmos(self) -> CosmosClient:
        if self._cosmos is None:
            credential = self.settings.azure_cosmos_key or self.identity
            self._cosmos = CosmosClient(
                self.settings.azure_cosmos_endpoint,
                credential=credential,
            )
        return self._cosmos

    def http(self) -> aiohttp.ClientSession:
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=8),
            )
        return self._http

    async def warm_credentials(self) -> None:
        scopes = []
        if (
            self.settings.azure_openai_endpoint
            and not self.settings.azure_openai_api_key
        ):
            scopes.append("https://cognitiveservices.azure.com/.default")
        if self.settings.azure_search_endpoint and not self.settings.azure_search_api_key:
            scopes.append("https://search.azure.com/.default")
        for scope in scopes:
            try:
                await self.identity.get_token(scope)
            except AzureError as exc:
                logger.warning("Azure credential warm-up failed for %s: %s", scope, exc)

    async def close(self) -> None:
        if self._http is not None:
            await self._http.close()
        if self._openai is not None:
            await self._openai.close()
        if self._search is not None:
            await self._search.close()
        if self._indexer is not None:
            await self._indexer.close()
        if self._blobs is not None:
            await self._blobs.close()
        if self._cosmos is not None:
            await self._cosmos.close()
        await self.identity.close()


@lru_cache
def get_azure_clients() -> AzureClients:
    return AzureClients(get_settings())

