import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from ..auth import require_user, user_id
from ..azure_clients import AzureClients, get_azure_clients
from ..config import Settings, get_settings
from ..dependencies import require_services
from ..models import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
    ConversationTurn,
    FeedbackRequest,
)
from ..services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    dependencies=[
        Depends(require_services("azureOpenAI", "azureAISearch", "azureCosmosDB"))
    ],
)
async def chat(
    body: ChatRequest,
    claims: dict = Depends(require_user),
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> ChatResponse:
    return await ChatService(settings, clients).answer(body, claims)


@router.get(
    "/history",
    response_model=list[ConversationSummary],
    dependencies=[Depends(require_services("azureCosmosDB"))],
)
async def history(
    claims: dict = Depends(require_user),
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> list[ConversationSummary]:
    container = clients.cosmos().get_database_client(
        settings.azure_cosmos_database
    ).get_container_client(settings.azure_cosmos_conversations_container)
    query = (
        "SELECT c.sessionId, c.question, c.createdAt FROM c "
        "WHERE c.userId = @userId ORDER BY c.createdAt DESC"
    )
    sessions: dict[str, dict] = {}
    async for item in container.query_items(
        query=query,
        parameters=[{"name": "@userId", "value": user_id(claims)}],
    ):
        session = sessions.setdefault(
            item["sessionId"],
            {
                "session_id": item["sessionId"],
                "title": item["question"][:80],
                "updated_at": item["createdAt"],
                "message_count": 0,
            },
        )
        session["message_count"] += 1
    return [ConversationSummary(**item) for item in sessions.values()]


@router.get(
    "/history/{session_id}",
    response_model=ConversationDetail,
    dependencies=[Depends(require_services("azureCosmosDB"))],
)
async def conversation(
    session_id: str,
    claims: dict = Depends(require_user),
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> ConversationDetail:
    container = clients.cosmos().get_database_client(
        settings.azure_cosmos_database
    ).get_container_client(settings.azure_cosmos_conversations_container)
    query = (
        "SELECT * FROM c WHERE c.userId = @userId AND c.sessionId = @sessionId "
        "ORDER BY c.createdAt ASC"
    )
    turns = []
    async for item in container.query_items(
        query=query,
        parameters=[
            {"name": "@userId", "value": user_id(claims)},
            {"name": "@sessionId", "value": session_id},
        ],
    ):
        turns.append(
            ConversationTurn(
                id=item["id"],
                created_at=item["createdAt"],
                question=item["question"],
                answer=item["answer"],
                citations=item.get("citations", []),
                grounded=item.get("grounded", False),
                latency_ms=item.get("latencyMs", 0),
            )
        )
    return ConversationDetail(session_id=session_id, turns=turns)


@router.post(
    "/feedback",
    status_code=204,
    dependencies=[Depends(require_services("azureCosmosDB"))],
)
async def feedback(
    body: FeedbackRequest,
    claims: dict = Depends(require_user),
    settings=Depends(get_settings),
    clients=Depends(get_azure_clients),
) -> None:
    container = clients.cosmos().get_database_client(
        settings.azure_cosmos_database
    ).get_container_client(settings.azure_cosmos_feedback_container)
    await container.create_item(
        {
            "id": str(uuid.uuid4()),
            "userId": user_id(claims),
            "sessionId": body.session_id,
            "messageId": body.message_id,
            "helpful": body.helpful,
            "comment": body.comment,
            "createdAt": datetime.now(UTC).isoformat(),
        }
    )
