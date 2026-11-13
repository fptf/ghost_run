import { useCallback } from "react";
import { useNavigate } from "react-router";

/** «Назад»: на предыдущий экран, если он из нашего приложения, иначе — на fallback. */
export function useBack(fallback: string) {
  const navigate = useNavigate();
  return useCallback(() => {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (idx > 0) navigate(-1);
    else navigate(fallback, { replace: true });
  }, [navigate, fallback]);
}
