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

/** Имя Web Lock, общего для всех вкладок сайта. */
export const REFRESH_LOCK = "auth-refresh";

async function requestAccessToken(): Promise<string | null> {
  try {
    const resp = await globalThis.fetch(`${apiBase()}/auth/refresh`, {
      method: "POST",
      credentials: "same-origin",
    });
    return resp.ok ? ((await resp.json()) as { access_token: string }).access_token : null;
  } catch {
    return null;
  }
}

/**
 * Refresh-токен одноразовый: сервер ротирует его на каждом обновлении, а повтор старого
 * считает кражей и отзывает сессию. Поэтому обновления из разных вкладок идут по очереди
 * под общей блокировкой: следующая вкладка отправит уже новую cookie, выставленную предыдущей.
 * Без Web Locks (старые браузеры) — как раньше, без блокировки.
 */
async function underRefreshLock(fn: () => Promise<string | null>): Promise<string | null> {
  const locks = globalThis.navigator?.locks;
  if (!locks) return fn();
  let token: string | null = null;
  await locks.request(REFRESH_LOCK, async () => {
    token = await fn();
  });
  return token;
}

/** Обновляет access-токен по refresh-cookie; параллельные вызовы делят один запрос. */
export function refreshAccessToken(): Promise<string | null> {
  refreshing ??= underRefreshLock(requestAccessToken)
    .catch(() => null)
    .then((token) => {
      tokenStore.set(token);
      return token;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

export function apiBase(): string {
  return `${globalThis.location?.origin ?? ""}/api`;
}
