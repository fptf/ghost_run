import createClient from "openapi-fetch";

import type { paths } from "./schema";

export const api = createClient<paths>({
  baseUrl: `${globalThis.location?.origin ?? ""}/api`,
  // Берём fetch в момент запроса, а не при создании клиента: так его можно подменить в тестах.
  fetch: (request) => globalThis.fetch(request),
});
