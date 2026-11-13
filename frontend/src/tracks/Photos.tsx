import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";

/** Фото подгружаются через API с токеном (тег img не умеет передавать Authorization). */
function PhotoImage({ trackId, photoId }: { trackId: string; photoId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    void api
      .GET("/tracks/{track_id}/photos/{photo_id}", {
        params: { path: { track_id: trackId, photo_id: photoId } },
        parseAs: "blob",
      })
      .then(({ data }) => {
        if (cancelled || !(data instanceof Blob)) return;
        url = URL.createObjectURL(data);
        setSrc(url);
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [trackId, photoId]);
  return src ? (
    <img src={src} alt="" className="photo" />
  ) : (
    <span className="photo photo--loading" />
  );
}

export function Photos({
  trackId,
  photos,
  onDelete,
}: {
  trackId: string;
  photos: { id: string }[];
  onDelete?: (photoId: string) => void;
}) {
  const { t } = useTranslation();
  if (photos.length === 0) return null;
  return (
    <div className="photos">
      {photos.map((p) => (
        <div key={p.id} className="photos__item">
          <PhotoImage trackId={trackId} photoId={p.id} />
          {onDelete && (
            <button
              type="button"
              className="photos__remove"
              aria-label={t("track.removePhoto")}
              onClick={() => onDelete(p.id)}
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
