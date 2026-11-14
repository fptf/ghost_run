/** Текст ошибки API: строковый `detail` из ответа сервера или запасной текст. */
export function errorDetail(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown } | null | undefined)?.detail;
  return typeof detail === "string" ? detail : fallback;
}

/** Сетевой сбой (fetch бросил исключение) как неуспешный ответ без тела: `.catch(() => NETWORK_FAILURE)`. */
export const NETWORK_FAILURE = { data: undefined, error: undefined, response: undefined } as const;
