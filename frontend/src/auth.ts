import type { AuthSession } from "./types";

const storageKey = "usms-auth-session";

export function loadSession(): AuthSession | null {
  try {
    const value = localStorage.getItem(storageKey);
    return value ? (JSON.parse(value) as AuthSession) : null;
  } catch {
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  localStorage.setItem(storageKey, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(storageKey);
}
