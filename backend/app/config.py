from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "USMS Saffron Azure Chatbot API"
    app_env: str = "development"
    allowed_origins: str = "http://localhost:5173"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = ""
    azure_openai_embedding_deployment: str = ""

    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index_name: str = ""
    azure_search_indexer_name: str = ""
    azure_search_semantic_configuration: str = "default"

    azure_storage_connection_string: str = ""
    azure_storage_account_url: str = ""
    azure_storage_container: str = "knowledge"

    azure_cosmos_endpoint: str = ""
    azure_cosmos_key: str = ""
    azure_cosmos_database: str = "usms-chatbot"
    azure_cosmos_users_container: str = "users"
    azure_cosmos_conversations_container: str = "conversations"
    azure_cosmos_feedback_container: str = "feedback"

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 480
    bootstrap_admin_username: str = "saffronadmin"
    bootstrap_admin_email: str = "aichatbot-admin@usmssaffron.onmicrosoft.com"
    bootstrap_admin_password: str = ""

    applicationinsights_connection_string: str = Field(
        default="", validation_alias="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )

    @property
    def origins(self) -> list[str]:
        return [value.strip() for value in self.allowed_origins.split(",") if value.strip()]

    def readiness(self) -> dict[str, list[str]]:
        checks = {
            "azureOpenAI": [
                "AZURE_OPENAI_ENDPOINT" if not self.azure_openai_endpoint else "",
                "AZURE_OPENAI_CHAT_DEPLOYMENT"
                if not self.azure_openai_chat_deployment
                else "",
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
                if not self.azure_openai_embedding_deployment
                else "",
            ],
            "azureAISearch": [
                "AZURE_SEARCH_ENDPOINT" if not self.azure_search_endpoint else "",
                "AZURE_SEARCH_INDEX_NAME" if not self.azure_search_index_name else "",
                "AZURE_SEARCH_INDEXER_NAME" if not self.azure_search_indexer_name else "",
            ],
            "azureBlobStorage": [
                "AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_URL"
                if not (
                    self.azure_storage_connection_string
                    or self.azure_storage_account_url
                )
                else ""
            ],
            "azureCosmosDB": [
                "AZURE_COSMOS_ENDPOINT" if not self.azure_cosmos_endpoint else ""
            ],
            "applicationAuthentication": [
                "JWT_SECRET_KEY" if not self.jwt_secret_key else "",
                "BOOTSTRAP_ADMIN_PASSWORD"
                if not self.bootstrap_admin_password
                else "",
            ],
        }
        return {name: [item for item in values if item] for name, values in checks.items()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
