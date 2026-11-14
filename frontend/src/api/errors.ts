/** Текст ошибки API: строковый `detail` из ответа сервера или запасной текст. */
export function errorDetail(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown } | null | undefined)?.detail;
  return typeof detail === "string" ? detail : fallback;
}
