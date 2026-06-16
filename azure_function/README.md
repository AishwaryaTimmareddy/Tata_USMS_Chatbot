# Azure Function: Knowledge Indexing Trigger

This Function implements the TSD ingestion orchestration:

```text
Azure Blob Storage
  -> Azure Function blob trigger
  -> Azure AI Search Indexer
  -> AI Search skillset and Azure OpenAI vectorization
  -> Azure AI Search index/vector store
```

The Function does not parse, chunk, or embed documents itself. Those operations
belong to the configured Azure AI Search indexer and skillset, which supports
incremental indexing and keeps enrichment logic centralized.

Configure native Blob soft-delete detection on the AI Search data source if
deleting a document in the admin portal must also remove its existing chunks
from the search index. Blob triggers handle create/update events; index cleanup
is an indexer data-source responsibility.

## Required application settings

- `AzureWebJobsStorage`: connection used by the Function blob trigger
- `AZURE_STORAGE_CONTAINER`: source blob container, normally `knowledge`
- `AZURE_SEARCH_ENDPOINT`: Azure AI Search service endpoint
- `AZURE_SEARCH_INDEXER_NAME`: configured blob indexer name
- `AZURE_SEARCH_API_KEY`: optional; omit when the Function managed identity has
  the required Azure AI Search data-plane role
- `APPLICATIONINSIGHTS_CONNECTION_STRING`: Function telemetry destination

For local execution, copy `local.settings.example.json` to
`local.settings.json` and fill in values after Azure resources are available.
