/** Access-токен живёт только в памяти (не в localStorage) — защита от XSS. */
type Listener = (token: string | null) => void;

let accessToken: string | null = null;
const listeners = new Set<Listener>();

export const tokenStore = {
  get: () => accessToken,
  set(token: string | null) {
    accessToken = token;
    listeners.forEach((l) => l(token));
  },
  subscribe(listener: Listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

let refreshing: Promise<string | null> | null = null;

/** Обновляет access-токен по refresh-cookie; параллельные вызовы делят один запрос. */
export function refreshAccessToken(): Promise<string | null> {
  refreshing ??= (async () => {
    try {
      const resp = await globalThis.fetch(`${apiBase()}/auth/refresh`, {
        method: "POST",
        credentials: "same-origin",
      });
      const token = resp.ok ? ((await resp.json()) as { access_token: string }).access_token : null;
      tokenStore.set(token);
      return token;
    } catch {
      tokenStore.set(null);
      return null;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

export function apiBase(): string {
  return `${globalThis.location?.origin ?? ""}/api`;
}
