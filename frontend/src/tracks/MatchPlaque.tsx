import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { api } from "../api/client";
import { formatDuration, formatKm } from "../lib/format";
import type { TrackDetail } from "./api";
import { verdictText } from "./verdict";

/** Плашка совпадения с маршрутом (по макету Preview): итог сравнения и «Не засчитывать». */
export function MatchPlaque({ track, visibility }: { track: TrackDetail; visibility: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const m = track.match;
  if (!m) return null;

  if (m.state === "detached") {
    return <p className="notice notice--info">{t("match.detached")}</p>;
  }
  // Приватные и «по ссылке» не сопоставляются: плашка исчезает (сценарий А).
  if (visibility !== "public") return null;

  const verdict = verdictText(t, m.diff_s, m.equal);

  async function onDetach() {
    setBusy(true);
    await api.PATCH("/tracks/{track_id}", {
      params: { path: { track_id: track.id } },
      body: { detach: true, publish: false },
    });
    setBusy(false);
    await queryClient.invalidateQueries({ queryKey: ["track", track.id] });
    void queryClient.invalidateQueries({ queryKey: ["group"] });
  }

  return (
    <section className="match-plaque" aria-label={t("match.title")}>
      <span className="match-plaque__label">
        {m.state === "active" ? t("match.counted") : t("match.title")}
      </span>
      <Link to={`/tracks/${m.root.id}`} className="match-plaque__route">
        {m.root.title ?? t("track.untitled")}
      </Link>
      <p>
        <strong>{formatDuration(m.result_time_s)}</strong> — {verdict}.{" "}
        {m.by_author ? t("match.ownRoute") : m.state === "pending" ? t("match.willJoin") : ""}
      </p>
      {m.trimmed && (
        <p className="match-plaque__note">
          {t("match.trimmed", {
            total: formatKm(track.distance_m),
            segment: formatKm(m.segment_distance_m),
          })}
        </p>
      )}
      {m.hidden_time_s > 1 && (
        <p className="match-plaque__note">
          {t("match.hiddenAdded", { time: formatDuration(m.hidden_time_s) })}
        </p>
      )}
      <button type="button" className="match-plaque__detach" disabled={busy} onClick={onDetach}>
        {t("match.detach")}
      </button>
    </section>
  );
}
