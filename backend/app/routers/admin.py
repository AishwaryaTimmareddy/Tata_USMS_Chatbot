from pathlib import PurePath
from urllib.parse import quote, unquote, urlparse
import logging

from azure.core.exceptions import AzureError, HttpResponseError
from azure.core.exceptions import ResourceNotFoundError
from azure.search.documents.models import QueryType
from azure.storage.blob import ContentSettings
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..auth import require_admin
from ..azure_clients import AzureClients, get_azure_clients
from ..config import Settings, get_settings
from ..dependencies import require_services
from ..models import DocumentItem, IndexerStatusResponse

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".txt"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def quote_search_filter_value(value: str) -> str:
    return value.replace("'", "''")


def source_blob_name(source: str | None) -> str | None:
    if not source:
        return None
    path = unquote(urlparse(source).path or source)
    return PurePath(path).name or None


def search_document_matches_file(
    result,
    filename: str,
    source_url: str | None = None,
) -> bool:
    title = result.get("title")
    source = result.get("source")
    return (
        title == filename
        or (source_url is not None and source == source_url)
        or source_blob_name(source) == filename
    )


def search_file_filter(filename: str, source_url: str | None = None) -> str:
    filters = [f"title eq '{quote_search_filter_value(filename)}'"]
    if source_url:
        filters.append(f"source eq '{quote_search_filter_value(source_url)}'")
    return " or ".join(filters)


def safe_document_name(filename: str) -> str:
    safe_name = PurePath(filename).name
    if not safe_name or safe_name != filename:
        raise HTTPException(400, "Invalid document name.")
    return safe_name


async def delete_search_documents(search_client, documents: list[dict]) -> int:
    deleted_count = 0
    for index in range(0, len(documents), 1000):
        batch = documents[index : index + 1000]
        await search_client.delete_documents(documents=batch)
        deleted_count += len(batch)
    return deleted_count


async def purge_document_from_search(
    source_url: str | None,
    title: str,
    settings: Settings,
    clients: AzureClients,
) -> int:
    if not settings.azure_search_index_name:
        return 0

    search_client = clients.search()
    deleted_count = 0
    search_filter = search_file_filter(title, source_url)
    while True:
        results = await search_client.search(
            search_text="*",
            filter=search_filter,
            select=["id", "title", "source"],
            top=1000,
            query_type=QueryType.SIMPLE,
        )
        documents = []
        async for result in results:
            document_id = result.get("id")
            if document_id and search_document_matches_file(result, title, source_url):
                documents.append({"id": document_id})

        if not documents:
            return deleted_count

        deleted_count += await delete_search_documents(search_client, documents)


async def purge_orphaned_search_documents(
    settings: Settings,
    clients: AzureClients,
) -> int:
    if not settings.azure_search_index_name:
        return 0

    container = clients.blobs().get_container_client(settings.azure_storage_container)
    active_names = set()
    active_sources = set()
    async for blob in container.list_blobs():
        active_names.add(blob.name)
        active_sources.add(container.get_blob_client(blob.name).url)

    search_client = clients.search()
    results = await search_client.search(
        search_text="*",
        select=["id", "title", "source"],
        query_type=QueryType.SIMPLE,
    )
    documents = []
    async for result in results:
        title = result.get("title")
        source = result.get("source")
        document_id = result.get("id")
        missing_by_title = title and title not in active_names
        missing_by_source = source and source not in active_sources
        source_name = source_blob_name(source)
        missing_by_source_name = source_name and source_name not in active_names
        if document_id and (missing_by_title or missing_by_source or missing_by_source_name):
            documents.append({"id": document_id})

    return await delete_search_documents(search_client, documents)


async def document_response(
    filename: str,
    disposition: str,
    settings: Settings,
    clients: AzureClients,
) -> StreamingResponse:
    safe_name = safe_document_name(filename)
    blob = clients.blobs().get_blob_client(
        container=settings.azure_storage_container,
        blob=safe_name,
    )
    try:
        properties = await blob.get_blob_properties()
        downloader = await blob.download_blob()
    except ResourceNotFoundError as exc:
        raise HTTPException(404, "Document not found.") from exc

    content_type = (
        properties.content_settings.content_type or "application/octet-stream"
    )
    encoded_name = quote(safe_name)
    return StreamingResponse(
        downloader.chunks(),
        media_type=content_type,
        headers={
            "Content-Disposition": (
                f"{disposition}; filename*=UTF-8''{encoded_name}"
            ),
            "Content-Length": str(properties.size),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/documents",
    response_model=list[DocumentItem],
    dependencies=[Depends(require_services("azureBlobStorage"))],
)
async def list_documents(
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> list[DocumentItem]:
    container = clients.blobs().get_container_client(settings.azure_storage_container)
    items = []
    async for blob in container.list_blobs(include=["metadata"]):
        items.append(
            DocumentItem(
                name=blob.name,
                size=blob.size,
                content_type=blob.content_settings.content_type,
                last_modified=blob.last_modified,
                url=container.get_blob_client(blob.name).url,
            )
        )
    return items


@router.post(
    "/documents",
    status_code=201,
    dependencies=[Depends(require_services("azureBlobStorage"))],
)
async def upload_document(
    file: UploadFile = File(...),
    category: str = "general",
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> dict:
    filename = PurePath(file.filename or "").name
    if not filename or PurePath(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Unsupported document type.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Document exceeds the 50 MB upload limit.")

    container = clients.blobs().get_container_client(settings.azure_storage_container)
    await container.upload_blob(
        name=filename,
        data=content,
        overwrite=True,
        metadata={"category": category, "approved": "true"},
        content_settings=ContentSettings(
            content_type=file.content_type or "application/octet-stream"
        ),
    )
    return {"name": filename, "status": "uploaded", "indexing": "pending"}


@router.delete(
    "/documents/{filename:path}",
    dependencies=[Depends(require_services("azureBlobStorage", "azureAISearch"))],
)
async def delete_document(
    filename: str,
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> dict:
    safe_name = safe_document_name(filename)
    container = clients.blobs().get_container_client(settings.azure_storage_container)
    blob = container.get_blob_client(safe_name)
    source_url = blob.url
    deleted = True
    try:
        await blob.delete_blob()
    except ResourceNotFoundError:
        deleted = False

    purged = 0
    cleanup_warning = None
    try:
        purged = await purge_document_from_search(source_url, safe_name, settings, clients)
    except Exception as exc:
        logger.warning("Search cleanup failed after document delete.", exc_info=exc)
        cleanup_warning = (
            "Document was removed from storage, but its Azure AI Search chunks could "
            "not be removed automatically. Run index cleanup again after confirming "
            "the app identity has Search Index Data Contributor access."
        )

    return {
        "name": safe_name,
        "status": "deleted" if deleted else "already_deleted",
        "purged": purged,
        "cleanup_warning": cleanup_warning,
    }


@router.get(
    "/documents/{filename:path}/view",
    dependencies=[Depends(require_services("azureBlobStorage"))],
)
async def view_document(
    filename: str,
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> StreamingResponse:
    return await document_response(filename, "inline", settings, clients)


@router.get(
    "/documents/{filename:path}/download",
    dependencies=[Depends(require_services("azureBlobStorage"))],
)
async def download_document(
    filename: str,
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> StreamingResponse:
    return await document_response(filename, "attachment", settings, clients)


@router.post(
    "/reindex",
    dependencies=[Depends(require_services("azureBlobStorage", "azureAISearch"))],
)
async def reindex(
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> dict:
    if not settings.azure_search_indexer_name:
        raise HTTPException(503, "AZURE_SEARCH_INDEXER_NAME is not configured.")
    purged = 0
    cleanup_warning = None
    try:
        purged = await purge_orphaned_search_documents(settings, clients)
    except Exception as exc:
        logger.warning("Search orphan cleanup failed before reindex.", exc_info=exc)
        cleanup_warning = (
            "Search cleanup did not complete before indexing. If deleted content "
            "still appears, confirm the app identity has Search Index Data "
            "Contributor and retry after RBAC propagation."
        )
    try:
        await clients.indexer().run_indexer(settings.azure_search_indexer_name)
    except AzureError as exc:
        error_detail = getattr(exc, "message", None) or str(exc)
        if (
            "Another indexer invocation is currently in progress" in error_detail
            or getattr(exc, "status_code", None) == 409
        ):
            return {
                "status": "already_running",
                "indexer": settings.azure_search_indexer_name,
                "purged": purged,
                "cleanup_warning": cleanup_warning,
            }
        raise HTTPException(
            status_code=502,
            detail=(
                "Azure AI Search indexer could not be started. Confirm the indexer "
                "exists and the app identity has Search Service Contributor access. "
                f"Azure error: {error_detail}"
            ),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error while starting Azure AI Search indexer.")
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected error while starting Azure AI Search indexer: {exc}",
        ) from exc
    return {
        "status": "started",
        "indexer": settings.azure_search_indexer_name,
        "purged": purged,
        "cleanup_warning": cleanup_warning,
    }


def _messages(items: list | None) -> list[str]:
    messages = []
    for item in items or []:
        message = getattr(item, "message", None) or getattr(item, "error_message", None)
        details = getattr(item, "details", None)
        if message and details:
            messages.append(f"{message} {details}")
        elif message:
            messages.append(message)
        elif details:
            messages.append(details)
    return messages


@router.get(
    "/reindex/status",
    response_model=IndexerStatusResponse,
    dependencies=[Depends(require_services("azureAISearch"))],
)
async def reindex_status(
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> IndexerStatusResponse:
    if not settings.azure_search_indexer_name:
        raise HTTPException(503, "AZURE_SEARCH_INDEXER_NAME is not configured.")
    try:
        status = await clients.indexer().get_indexer_status(
            settings.azure_search_indexer_name
        )
    except HttpResponseError as exc:
        error_detail = exc.message or str(exc)
        raise HTTPException(
            status_code=502,
            detail=f"Azure AI Search indexer status could not be read. Azure error: {error_detail}",
        ) from exc

    last_result = getattr(status, "last_result", None)
    return IndexerStatusResponse(
        status=str(getattr(status, "status", "unknown")),
        last_result=str(getattr(last_result, "status", "")) if last_result else None,
        processed=int(getattr(last_result, "item_count", 0) or 0) if last_result else 0,
        failed=int(getattr(last_result, "failed_item_count", 0) or 0)
        if last_result
        else 0,
        errors=_messages(getattr(last_result, "errors", None)) if last_result else [],
        warnings=_messages(getattr(last_result, "warnings", None)) if last_result else [],
    )
