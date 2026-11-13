import { useCallback } from "react";

import { api } from "../api/client";

/** Скачивание GPX через API (с токеном, если он есть) и сохранение файла. */
export function useGpxDownload() {
  return useCallback(async (trackId: string, title: string | null) => {
    const { data, response } = await api.GET("/tracks/{track_id}/gpx", {
      params: { path: { track_id: trackId } },
      parseAs: "blob",
    });
    if (!response.ok || !(data instanceof Blob)) return false;
    const url = URL.createObjectURL(data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(title ?? "route").replace(/[\\/:*?"<>|]+/g, " ").trim() || "route"}.gpx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return true;
  }, []);
}
