import { FormEvent, useState } from "react";
import { LoaderCircle, LockKeyhole, Mail, UserRound } from "lucide-react";
import { login, register } from "../api";
import type { AuthSession } from "../types";

export function LoginPanel({
  onAuthenticated,
}: {
  onAuthenticated: (session: AuthSession) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session =
        mode === "login"
          ? await login(email, password)
          : await register(displayName, email, password);
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
        <h1>Trusted answers from approved saffron knowledge.</h1>
        <p>
          Sign in to ask questions and continue your previous conversations across sessions.
        </p>
      </section>

      <section className="login-card">
        <span className="eyebrow">{mode === "login" ? "WELCOME BACK" : "CREATE ACCOUNT"}</span>
        <h2>{mode === "login" ? "Sign in" : "Register"}</h2>
        <p>
          {mode === "login"
            ? "Use your account email and password."
            : "Create an account to use the knowledge assistant."}
        </p>
        <form onSubmit={submit}>
          {mode === "register" && (
            <label>
              Display name
              <span><UserRound size={16} /><input required minLength={2} value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></span>
            </label>
          )}
          <label>
            Email or admin username
            <span><Mail size={16} /><input required value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" /></span>
          </label>
          <label>
            Password
            <span><LockKeyhole size={16} /><input required minLength={8} type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} /></span>
          </label>
          {error && <div className="error-banner">{error}</div>}
          <button className="primary-button login-submit" disabled={busy}>
            {busy && <LoaderCircle size={17} className="spin" />}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <button
          className="auth-switch"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
        >
          {mode === "login" ? "New user? Create an account" : "Already registered? Sign in"}
        </button>
      </section>
    </main>
  );
}
