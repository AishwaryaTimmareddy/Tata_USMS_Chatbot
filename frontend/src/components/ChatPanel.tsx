import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Check,
  ChevronDown,
  FileText,
  History,
  LoaderCircle,
  RotateCcw,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { getConversation, listHistory, sendChat, sendFeedback } from "../api";
import type { ConversationSummary, Message } from "../types";

const starters = [
  "What saffron variants are available?",
  "How long does delivery usually take?",
  "What is the cancellation policy?",
  "How should saffron be stored?",
];

const welcome: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Namaste. I can help with USMS Saffron products, delivery, returns, and approved policies. What would you like to know?",
  grounded: true,
};

const anonymousHistoryKey = "usms-anonymous-chat-history";
const anonymousSessionKey = "usms-anonymous-session-id";

function loadAnonymousMessages(): Message[] {
  try {
    const raw = localStorage.getItem(anonymousHistoryKey);
    if (!raw) return [welcome];
    const parsed = JSON.parse(raw) as Message[];
    return parsed.length ? parsed : [welcome];
  } catch {
    return [welcome];
  }
}

function loadAnonymousSessionId(): string | null {
  try {
    return localStorage.getItem(anonymousSessionKey);
  } catch {
    return null;
  }
}

function saveAnonymousState(messages: Message[], sessionId: string | null): void {
  try {
    localStorage.setItem(anonymousHistoryKey, JSON.stringify(messages));
    if (sessionId) {
      localStorage.setItem(anonymousSessionKey, sessionId);
    } else {
      localStorage.removeItem(anonymousSessionKey);
    }
  } catch {
    return;
  }
}

export function ChatPanel({
  token,
  authenticated,
}: {
  token: string | null;
  authenticated: boolean;
}) {
  const [messages, setMessages] = useState<Message[]>(() =>
    authenticated ? [welcome] : loadAnonymousMessages(),
  );
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(() =>
    authenticated ? null : loadAnonymousSessionId(),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [feedbackByMessage, setFeedbackByMessage] = useState<
    Record<string, "saving" | "helpful" | "notHelpful" | "error">
  >({});
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (authenticated) {
      setMessages([welcome]);
      setSessionId(null);
      setFeedbackByMessage({});
      setError("");
      return;
    }
    setMessages(loadAnonymousMessages());
    setSessionId(loadAnonymousSessionId());
    setFeedbackByMessage({});
    setError("");
  }, [authenticated]);

  useEffect(() => {
    if (!authenticated) {
      saveAnonymousState(messages, sessionId);
    }
  }, [authenticated, messages, sessionId]);

  useEffect(() => {
    if (!authenticated) {
      setConversations([]);
      return;
    }
    if (!token) return;
    void listHistory(token).then(setConversations).catch(() => undefined);
  }, [authenticated, token]);

  async function refreshHistory() {
    if (!authenticated || !token) {
      setConversations([]);
      return;
    }
    setConversations(await listHistory(token));
  }

  async function submit(event?: FormEvent, preset?: string) {
    event?.preventDefault();
    const question = (preset ?? input).trim();
    if (!question || loading) return;
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setError("");
    setLoading(true);
    try {
      const result = await sendChat(token, question, sessionId);
      setSessionId(result.session_id);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: result.answer,
          citations: result.citations,
          grounded: result.grounded,
          latency: result.latency_ms,
        },
      ]);
      if (authenticated) {
        await refreshHistory();
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The request failed.");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setMessages([welcome]);
    setSessionId(null);
    setError("");
    setFeedbackByMessage({});
    if (!authenticated) {
      saveAnonymousState([welcome], null);
    }
  }

  async function feedback(messageId: string, helpful: boolean) {
    if (!sessionId) return;
    let comment: string | undefined;
    let contact: string | undefined;
    if (!helpful) {
      comment =
        window.prompt("Please tell us what was wrong or missing.")?.trim() || undefined;
      contact =
        window
          .prompt("Optional: share your email or mobile number for follow-up.")
          ?.trim() || undefined;
    }

    setFeedbackByMessage((current) => ({ ...current, [messageId]: "saving" }));
    try {
      await sendFeedback(token, sessionId, messageId, helpful, comment, contact);
      setFeedbackByMessage((current) => ({
        ...current,
        [messageId]: helpful ? "helpful" : "notHelpful",
      }));
    } catch {
      setFeedbackByMessage((current) => ({ ...current, [messageId]: "error" }));
    }
  }

  async function openConversation(id: string) {
    if (!authenticated || !token) return;
    setLoading(true);
    setError("");
    try {
      const detail = await getConversation(token, id);
      const restored: Message[] = detail.turns.flatMap((turn) => [
        {
          id: `${turn.id}-user`,
          role: "user" as const,
          content: turn.question,
        },
        {
          id: `${turn.id}-assistant`,
          role: "assistant" as const,
          content: turn.answer,
          citations: turn.citations,
          grounded: turn.grounded,
          latency: turn.latency_ms,
        },
      ]);
      setSessionId(id);
      setMessages(restored.length ? restored : [welcome]);
      setFeedbackByMessage({});
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "History could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-layout">
      <header className="page-header">
        <div>
          <span className="eyebrow">CUSTOMER EXPERIENCE</span>
          <h1>Saffron knowledge assistant</h1>
          <p>Answers grounded in approved USMS product and policy documents.</p>
        </div>
        <button className="secondary-button" onClick={reset}>
          <RotateCcw size={16} /> Clear conversation
        </button>
      </header>

      <div className={authenticated ? "chat-columns" : "chat-columns public-chat"}>
        {authenticated && (
          <aside className="history-card">
            <div className="history-heading">
              <History size={17} />
              <strong>Previous chats</strong>
            </div>
            <button className="new-chat-button" onClick={reset}>
              + Start a new conversation
            </button>
            <div className="history-list">
              <>
                {conversations.map((conversation) => (
                  <button
                    className={
                      conversation.session_id === sessionId
                        ? "history-item active"
                        : "history-item"
                    }
                    key={conversation.session_id}
                    onClick={() => openConversation(conversation.session_id)}
                  >
                    <strong>{conversation.title}</strong>
                    <span>{conversation.message_count} messages</span>
                  </button>
                ))}
                {!conversations.length && <p>No previous conversations yet.</p>}
              </>
            </div>
          </aside>
        )}
        <div className="chat-card">
          <div className="chat-topbar">
            <div className="assistant-avatar">
              <Sparkles size={19} />
            </div>
            <div>
              <strong>USMS Assistant</strong>
              <span>
                <i /> {authenticated ? "Signed-in admin" : "Public visitor"}
              </span>
            </div>
            <div className="chat-trust">
              <Check size={14} /> Approved sources only
            </div>
          </div>

          <div className="message-list">
            {messages.map((message) => (
              <article key={message.id} className={`message-row ${message.role}`}>
                {message.role === "assistant" && (
                  <div className="message-avatar">
                    <Sparkles size={16} />
                  </div>
                )}
                <div className="message-content">
                  <div className="message-bubble">{message.content}</div>
                  {message.citations && message.citations.length > 0 && (
                    <details className="citations">
                      <summary>
                        <FileText size={15} />
                        {message.citations.length} approved source
                        {message.citations.length > 1 ? "s" : ""}
                        <ChevronDown size={15} />
                      </summary>
                      <div className="citation-list">
                        {message.citations.map((citation, index) => (
                          <div className="citation" key={`${citation.source}-${index}`}>
                            <span>{index + 1}</span>
                            <div>
                              <strong>{citation.title}</strong>
                              <p>{citation.excerpt}...</p>
                              {citation.page_number && (
                                <small>Page {citation.page_number}</small>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                  {message.role === "assistant" && message.id !== "welcome" && (
                    <div className="message-meta">
                      <span>{message.latency ? `${(message.latency / 1000).toFixed(1)}s` : ""}</span>
                      <button
                        aria-label="Helpful"
                        className={feedbackByMessage[message.id] === "helpful" ? "active" : ""}
                        disabled={feedbackByMessage[message.id] === "saving"}
                        onClick={() => feedback(message.id, true)}
                      >
                        <ThumbsUp size={14} />
                      </button>
                      <button
                        aria-label="Not helpful"
                        className={feedbackByMessage[message.id] === "notHelpful" ? "active" : ""}
                        disabled={feedbackByMessage[message.id] === "saving"}
                        onClick={() => feedback(message.id, false)}
                      >
                        <ThumbsDown size={14} />
                      </button>
                      {feedbackByMessage[message.id] === "saving" && <small>Saving...</small>}
                      {(feedbackByMessage[message.id] === "helpful" ||
                        feedbackByMessage[message.id] === "notHelpful") && (
                        <small>Feedback saved</small>
                      )}
                      {feedbackByMessage[message.id] === "error" && <small>Feedback failed</small>}
                    </div>
                  )}
                </div>
              </article>
            ))}

            {messages.length === 1 && (
              <div className="starter-grid">
                {starters.map((starter) => (
                  <button key={starter} onClick={() => submit(undefined, starter)}>
                    {starter}
                  </button>
                ))}
              </div>
            )}

            {loading && (
              <div className="message-row assistant">
                <div className="message-avatar">
                  <Sparkles size={16} />
                </div>
                <div className="typing">
                  <i />
                  <i />
                  <i />
                </div>
              </div>
            )}
            {error && <div className="error-banner">{error}</div>}
            <div ref={bottomRef} />
          </div>

          <form className="composer" onSubmit={submit}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submit();
                }
              }}
              placeholder="Ask about products, delivery, cancellations, or returns..."
              rows={1}
            />
            <button type="submit" disabled={!input.trim() || loading} aria-label="Send message">
              {loading ? <LoaderCircle className="spin" size={19} /> : <ArrowUp size={19} />}
            </button>
          </form>
          <p className="disclaimer">
            AI-generated answers may require verification. This assistant cannot access or modify orders.
          </p>
        </div>
      </div>
    </div>
  );
}
