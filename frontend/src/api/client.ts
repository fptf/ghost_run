import createClient from "openapi-fetch";

import { apiBase, refreshAccessToken, tokenStore } from "../auth/tokenStore";
import type { paths } from "./schema";

function withAuth(request: Request, token: string | null): Request {
  const req = request.clone();
  if (token) req.headers.set("Authorization", `Bearer ${token}`);
  return req;
}

/**
 * Добавляет access-токен и один раз повторяет запрос после 401, обновив токен.
 * Пока сессия при загрузке страницы ещё восстанавливается, запрос ждёт этого (делит тот же
 * /auth/refresh): иначе свой приватный трек по прямой ссылке ушёл бы без токена и выглядел
 * отсутствующим. Гость ждёт только этот один refresh — дальше сессия считается известной.
 */
async function authFetch(request: Request): Promise<Response> {
  const isAuthCall = new URL(request.url).pathname.includes("/auth/");
  let token = tokenStore.get();
  if (!token && !isAuthCall && !tokenStore.isResolved()) token = await refreshAccessToken();
  // Берём fetch в момент запроса, а не при создании клиента: так его можно подменить в тестах.
  const response = await globalThis.fetch(withAuth(request, token));
  if (response.status !== 401 || !token || isAuthCall) {
    return response;
  }
  const fresh = await refreshAccessToken();
  return fresh ? globalThis.fetch(withAuth(request, fresh)) : response;
}

export const api = createClient<paths>({ baseUrl: apiBase(), fetch: authFetch });

export type Schemas = import("./schema").components["schemas"];
