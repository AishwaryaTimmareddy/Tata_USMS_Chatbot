import { useState } from "react";
import { BookOpen, LogOut, MessageCircle, Settings, UserRound } from "lucide-react";
import { clearSession, loadSession, saveSession } from "./auth";
import { AdminPanel } from "./components/AdminPanel";
import { ChatPanel } from "./components/ChatPanel";
import { LoginPanel } from "./components/LoginPanel";
import { ReadinessPanel } from "./components/ReadinessPanel";
import type { AuthSession } from "./types";

type View = "chat" | "admin" | "settings";

export default function App() {
  const [session, setSession] = useState<AuthSession | null>(() => loadSession());
  const [view, setView] = useState<View>("chat");

  function authenticated(value: AuthSession) {
    saveSession(value);
    setSession(value);
  }

  function logout() {
    clearSession();
    setSession(null);
    setView("chat");
  }

  if (!session) return <LoginPanel onAuthenticated={authenticated} />;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">S</div>
          <div>
            <strong>USMS Saffron</strong>
            <span>Knowledge Assistant</span>
          </div>
        </div>

        <nav aria-label="Main navigation">
          <button
            className={view === "chat" ? "nav-item active" : "nav-item"}
            onClick={() => setView("chat")}
          >
            <MessageCircle size={19} /> Chat and history
          </button>
          {session.user.role === "admin" && (
            <button
              className={view === "admin" ? "nav-item active" : "nav-item"}
              onClick={() => setView("admin")}
            >
              <BookOpen size={19} /> Knowledge base
            </button>
          )}
          {session.user.role === "admin" && (
            <button
              className={view === "settings" ? "nav-item active" : "nav-item"}
              onClick={() => setView("settings")}
            >
              <Settings size={19} /> Azure readiness
            </button>
          )}
        </nav>

        <div className="account-card">
          <UserRound size={18} />
          <div>
            <strong>{session.user.display_name}</strong>
            <span>{session.user.role === "admin" ? "Administrator" : session.user.email}</span>
          </div>
          <button onClick={logout} aria-label="Sign out"><LogOut size={16} /></button>
        </div>
      </aside>

      <section className="workspace">
        {view === "chat" && <ChatPanel token={session.access_token} />}
        {view === "admin" && session.user.role === "admin" && (
          <AdminPanel token={session.access_token} />
        )}
        {view === "settings" && session.user.role === "admin" && <ReadinessPanel />}
      </section>
    </main>
  );
}

