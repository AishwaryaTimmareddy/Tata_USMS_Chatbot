import asyncio

from app.config import Settings
from app.routers.admin import purge_document_from_search, search_file_filter


class AsyncResults:
    def __init__(self, documents):
        self.documents = iter(documents)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.documents)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeSearchClient:
    def __init__(self):
        self.deleted_batches = []
        self.search_calls = []
        self.responses = [
            [
                {
                    "id": "chunk-1",
                    "title": "policy.pdf",
                    "source": "https://example.blob.core.windows.net/knowledge/policy.pdf",
                },
                {
                    "id": "chunk-2",
                    "title": "policy.pdf",
                    "source": "https://example.blob.core.windows.net/knowledge/policy.pdf",
                },
            ],
            [],
        ]

    async def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return AsyncResults(self.responses.pop(0))

    async def delete_documents(self, documents):
        self.deleted_batches.append(documents)


class FakeClients:
    def __init__(self, search_client):
        self.search_client = search_client

    def search(self):
        return self.search_client


def test_search_file_filter_escapes_values():
    assert search_file_filter("O'Brien.pdf", "https://example/O'Brien.pdf") == (
        "title eq 'O''Brien.pdf' or source eq 'https://example/O''Brien.pdf'"
    )


def test_purge_document_from_search_filters_and_deletes_matching_chunks():
    search_client = FakeSearchClient()
    settings = Settings(_env_file=None, azure_search_index_name="knowledge")

    deleted = asyncio.run(
        purge_document_from_search(
            "https://example.blob.core.windows.net/knowledge/policy.pdf",
            "policy.pdf",
            settings,
            FakeClients(search_client),
        )
    )

    assert deleted == 2
    assert search_client.search_calls[0]["filter"] == (
        "title eq 'policy.pdf' or source eq "
        "'https://example.blob.core.windows.net/knowledge/policy.pdf'"
    )
    assert search_client.deleted_batches == [[{"id": "chunk-1"}, {"id": "chunk-2"}]]
