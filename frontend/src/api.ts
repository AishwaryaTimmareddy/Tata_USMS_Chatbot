import type {
  AuthSession,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  DocumentItem,
  Health,
  IndexerStatus,
} from "./types";

const apiBase = import.meta.env.VITE_API_BASE_URL || "/api";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message || `Request failed with status ${response.status}.`;
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<Health> {
  return parseResponse(await fetch(`${apiBase}/health`));
}

export async function sendChat(
  token: string | null,
  message: string,
  sessionId: string | null,
): Promise<ChatResponse> {
  return parseResponse(
    await fetch(`${apiBase}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({
        message,
        session_id: sessionId,
      }),
    }),
  );
}

export async function sendFeedback(
  token: string | null,
  sessionId: string,
  messageId: string,
  helpful: boolean,
  comment?: string,
  contact?: string,
): Promise<void> {
  return parseResponse(
    await fetch(`${apiBase}/chat/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({
        session_id: sessionId,
        message_id: messageId,
        helpful,
        comment,
        contact,
      }),
    }),
  );
}

function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function login(email: string, password: string): Promise<AuthSession> {
  return parseResponse(
    await fetch(`${apiBase}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  );
}

export async function register(
  displayName: string,
  email: string,
  password: string,
): Promise<AuthSession> {
  return parseResponse(
    await fetch(`${apiBase}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName, email, password }),
    }),
  );
}

export async function listHistory(token: string): Promise<ConversationSummary[]> {
  return parseResponse(
    await fetch(`${apiBase}/chat/history`, { headers: authHeaders(token) }),
  );
}

export async function getConversation(
  token: string,
  sessionId: string,
): Promise<ConversationDetail> {
  return parseResponse(
    await fetch(`${apiBase}/chat/history/${encodeURIComponent(sessionId)}`, {
      headers: authHeaders(token),
    }),
  );
}

export async function listDocuments(token: string): Promise<DocumentItem[]> {
  return parseResponse(
    await fetch(`${apiBase}/admin/documents`, { headers: authHeaders(token) }),
  );
}

export async function uploadDocument(
  token: string,
  file: File,
  category: string,
): Promise<void> {
  const body = new FormData();
  body.append("file", file);
  return parseResponse(
    await fetch(
      `${apiBase}/admin/documents?category=${encodeURIComponent(category)}`,
      { method: "POST", headers: authHeaders(token), body },
    ),
  );
}

export async function deleteDocument(token: string, name: string): Promise<void> {
  return parseResponse(
    await fetch(`${apiBase}/admin/documents/${encodeURIComponent(name)}`, {
      method: "DELETE",
      headers: authHeaders(token),
    }),
  );
}

async function fetchDocument(
  token: string,
  name: string,
  action: "view" | "download",
): Promise<Blob> {
  const response = await fetch(
    `${apiBase}/admin/documents/${encodeURIComponent(name)}/${action}`,
    { headers: authHeaders(token) },
  );
  if (!response.ok) {
    await parseResponse(response);
  }
  return response.blob();
}

export async function viewDocument(token: string, name: string): Promise<void> {
  const target = window.open("", "_blank", "noopener,noreferrer");
  try {
    const blob = await fetchDocument(token, name, "view");
    const url = URL.createObjectURL(blob);
    if (target) {
      target.location.href = url;
    } else {
      window.open(url, "_blank", "noopener,noreferrer");
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (error) {
    target?.close();
    throw error;
  }
}

export async function downloadDocument(token: string, name: string): Promise<void> {
  const blob = await fetchDocument(token, name, "download");
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function runIndexer(token: string): Promise<void> {
  return parseResponse(
    await fetch(`${apiBase}/admin/reindex`, {
      method: "POST",
      headers: authHeaders(token),
    }),
  );
}

export async function getIndexerStatus(token: string): Promise<IndexerStatus> {
  return parseResponse(
    await fetch(`${apiBase}/admin/reindex/status`, {
      headers: authHeaders(token),
    }),
  );
}
