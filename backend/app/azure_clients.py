from functools import lru_cache

from azure.core.credentials import AzureKeyCredential
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexerClient
from azure.storage.blob.aio import BlobServiceClient
from openai import AsyncAzureOpenAI

from .config import Settings, get_settings


class AzureClients:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.identity = DefaultAzureCredential()

    def openai(self) -> AsyncAzureOpenAI:
        kwargs = {
            "azure_endpoint": self.settings.azure_openai_endpoint,
            "api_version": self.settings.azure_openai_api_version,
        }
        if self.settings.azure_openai_api_key:
            kwargs["api_key"] = self.settings.azure_openai_api_key
        else:
            from azure.identity.aio import get_bearer_token_provider

            kwargs["azure_ad_token_provider"] = get_bearer_token_provider(
                self.identity, "https://cognitiveservices.azure.com/.default"
            )
        return AsyncAzureOpenAI(**kwargs)

    def search_credential(self):
        if self.settings.azure_search_api_key:
            return AzureKeyCredential(self.settings.azure_search_api_key)
        return self.identity

    def search(self) -> SearchClient:
        return SearchClient(
            endpoint=self.settings.azure_search_endpoint,
            index_name=self.settings.azure_search_index_name,
            credential=self.search_credential(),
        )

    def indexer(self) -> SearchIndexerClient:
        return SearchIndexerClient(
            endpoint=self.settings.azure_search_endpoint,
            credential=self.search_credential(),
        )

    def blobs(self) -> BlobServiceClient:
        if self.settings.azure_storage_connection_string:
            return BlobServiceClient.from_connection_string(
                self.settings.azure_storage_connection_string
            )
        return BlobServiceClient(
            account_url=self.settings.azure_storage_account_url,
            credential=self.identity,
        )

    def cosmos(self) -> CosmosClient:
        credential = self.settings.azure_cosmos_key or self.identity
        return CosmosClient(self.settings.azure_cosmos_endpoint, credential=credential)


@lru_cache
def get_azure_clients() -> AzureClients:
    return AzureClients(get_settings())

