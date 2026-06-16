import logging
import os

import azure.functions as func
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexerClient

app = func.FunctionApp()


def _indexer_client() -> SearchIndexerClient:
    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    api_key = os.getenv("AZURE_SEARCH_API_KEY")
    credential = (
        AzureKeyCredential(api_key)
        if api_key
        else DefaultAzureCredential()
    )
    return SearchIndexerClient(endpoint=endpoint, credential=credential)


@app.blob_trigger(
    arg_name="document",
    path="%AZURE_STORAGE_CONTAINER%/{name}",
    connection="DocumentStorage",
)
def trigger_knowledge_indexing(document: func.InputStream) -> None:
    """Start the AI Search indexer when an approved document changes."""
    indexer_name = os.environ["AZURE_SEARCH_INDEXER_NAME"]
    logging.info(
        "Knowledge document detected: name=%s, bytes=%s",
        document.name,
        document.length,
    )

    try:
        _indexer_client().run_indexer(indexer_name)
        logging.info("Azure AI Search indexer '%s' started.", indexer_name)
    except HttpResponseError as exc:
        if exc.status_code == 409:
            # Multiple uploads can arrive while the same incremental indexer run
            # is active. The active run will detect all changed blobs.
            logging.info(
                "Indexer '%s' is already running; no duplicate run was started.",
                indexer_name,
            )
            return
        logging.exception("Unable to start Azure AI Search indexing.")
        raise
