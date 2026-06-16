from app.config import Settings


def test_readiness_reports_missing_azure_configuration():
    settings = Settings(_env_file=None)
    readiness = settings.readiness()

    assert "AZURE_OPENAI_ENDPOINT" in readiness["azureOpenAI"]
    assert "AZURE_SEARCH_ENDPOINT" in readiness["azureAISearch"]
    assert readiness["azureBlobStorage"]
    assert readiness["azureCosmosDB"]


def test_readiness_accepts_managed_identity_configuration():
    settings = Settings(
        _env_file=None,
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_chat_deployment="chat",
        azure_openai_embedding_deployment="embedding",
        azure_search_endpoint="https://example.search.windows.net",
        azure_search_index_name="knowledge",
        azure_search_indexer_name="knowledge-indexer",
        azure_storage_account_url="https://example.blob.core.windows.net",
        azure_cosmos_endpoint="https://example.documents.azure.com",
        jwt_secret_key="test-secret",
        bootstrap_admin_password="test-admin-password",
    )

    assert all(not missing for missing in settings.readiness().values())
