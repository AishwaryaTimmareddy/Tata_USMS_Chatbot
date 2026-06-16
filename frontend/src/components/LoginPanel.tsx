import { FormEvent, useState } from "react";
import { ArrowLeft, LoaderCircle, LockKeyhole, Mail } from "lucide-react";
import { login } from "../api";
import type { AuthSession } from "../types";

export function LoginPanel({
  onAuthenticated,
  onCancel,
}: {
  onAuthenticated: (session: AuthSession) => void;
  onCancel: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session = await login(email, password);
      onAuthenticated(session);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-intro">
        <div className="brand large">
          <div className="brand-mark">S</div>
          <div>
            <strong>USMS Saffron</strong>
            <span>Knowledge Assistant</span>
          </div>
        </div>
        <h1>Anonymous visitors can ask questions. Admins manage the knowledge base.</h1>
        <p>
          Use the public assistant for customer queries. Sign in only for document management,
          indexing, and Azure readiness checks.
        </p>
      </section>

      <section className="login-card">
        <span className="eyebrow">ADMIN ACCESS</span>
        <h2>Sign in</h2>
        <p>Use the administrator username or email and password.</p>
        <form onSubmit={submit}>
          <label>
            Email or admin username
            <span><Mail size={16} /><input required value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" /></span>
          </label>
          <label>
            Password
            <span><LockKeyhole size={16} /><input required minLength={8} type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" /></span>
          </label>
          {error && <div className="error-banner">{error}</div>}
          <button className="primary-button login-submit" disabled={busy}>
            {busy && <LoaderCircle size={17} className="spin" />}
            Sign in
          </button>
        </form>
        <button className="auth-switch" onClick={onCancel}>
          <ArrowLeft size={14} /> Back to public chat
        </button>
      </section>
    </main>
  );
}
