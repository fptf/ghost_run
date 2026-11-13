import { useCallback, useEffect, useRef } from "react";
import { useSearchParams } from "react-router";

/**
 * Как useSearchParams, но обновления применяются последовательно к самым свежим параметрам.
 *
 * Функциональный setter React Router получает параметры из последней отрисовки: если карта
 * сообщает о сдвиге сразу после сброса (ещё до перерисовки), старые фильтры вернулись бы в адрес.
 */
export function useUrlParams() {
  const [params, setParams] = useSearchParams();
  const latest = useRef(params);
  useEffect(() => {
    latest.current = params;
  }, [params]);

  const update = useCallback(
    (fn: (p: URLSearchParams) => URLSearchParams, replace = true) => {
      const next = fn(new URLSearchParams(latest.current));
      latest.current = next;
      setParams(next, { replace });
    },
    [setParams],
  );
  return [params, update] as const;
}
