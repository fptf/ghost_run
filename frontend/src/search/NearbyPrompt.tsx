import { useState } from "react";
import { useTranslation } from "react-i18next";

import { locate, setHomeView, setNearbyAnswer } from "./homeView";
import type { View } from "./params";

const NEARBY_ZOOM = 13;

/**
 * «Показать треки рядом?» поверх карты. Согласие запоминается вместе с найденной областью —
 * она становится исходной для главной; при ошибке геолокации — короткая подсказка.
 */
export function NearbyPrompt({
  initiallyOpen,
  onLocated,
}: {
  initiallyOpen: boolean;
  onLocated: (view: View) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(initiallyOpen);
  const [failed, setFailed] = useState(false);

  async function answer(yes: boolean) {
    setOpen(false);
    setNearbyAnswer(yes ? "accepted" : "declined");
    if (!yes) return;
    try {
      const pos = await locate();
      const view = { lat: pos.lat, lon: pos.lon, z: NEARBY_ZOOM };
      setHomeView(view);
      onLocated(view);
    } catch {
      setFailed(true);
      window.setTimeout(() => setFailed(false), 5000);
    }
  }

  return (
    <>
      {open && (
        <div
          className="map-float map-float--prompt"
          role="dialog"
          aria-label={t("search.nearbyQuestion")}
        >
          <strong>{t("search.nearbyQuestion")}</strong>
          <div className="row">
            <button
              type="button"
              className="btn btn--primary btn--sm"
              onClick={() => void answer(true)}
            >
              {t("search.nearbyYes")}
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => void answer(false)}
            >
              {t("search.nearbyNo")}
            </button>
          </div>
        </div>
      )}
      {failed && (
        <p role="status" className="notice notice--info map-float map-float--prompt">
          {t("search.nearbyFailed")}
        </p>
      )}
    </>
  );
}
