from pathlib import PurePath
from urllib.parse import quote

from azure.core.exceptions import HttpResponseError
from azure.core.exceptions import ResourceNotFoundError
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

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".txt"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def safe_document_name(filename: str) -> str:
    safe_name = PurePath(filename).name
    if not safe_name or safe_name != filename:
        raise HTTPException(400, "Invalid document name.")
    return safe_name


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
    status_code=204,
    dependencies=[Depends(require_services("azureBlobStorage"))],
)
async def delete_document(
    filename: str,
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> None:
    safe_name = safe_document_name(filename)
    container = clients.blobs().get_container_client(settings.azure_storage_container)
    try:
        await container.delete_blob(safe_name)
    except ResourceNotFoundError as exc:
        raise HTTPException(404, "Document not found.") from exc


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
    dependencies=[Depends(require_services("azureAISearch"))],
)
async def reindex(
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> dict:
    if not settings.azure_search_indexer_name:
        raise HTTPException(503, "AZURE_SEARCH_INDEXER_NAME is not configured.")
    try:
        await clients.indexer().run_indexer(settings.azure_search_indexer_name)
    except HttpResponseError as exc:
        error_detail = exc.message or str(exc)
        raise HTTPException(
            status_code=502,
            detail=(
                "Azure AI Search indexer could not be started. Confirm the indexer "
                "exists and the app identity has Search Service Contributor access. "
                f"Azure error: {error_detail}"
            ),
        ) from exc
    return {"status": "started", "indexer": settings.azure_search_indexer_name}


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
