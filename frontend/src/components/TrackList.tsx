import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { categoryLabel, formatDate, formatDuration, formatKm, formatPace } from "../lib/format";
import type { TrackSummary } from "../tracks/api";

export function TrackList({
  tracks,
  empty,
  showStatus = false,
}: {
  tracks: TrackSummary[];
  empty: string;
  showStatus?: boolean;
}) {
  const { t } = useTranslation();
  if (tracks.length === 0) return <div className="empty">{empty}</div>;
  return (
    <ul className="track-list">
      {tracks.map((tr) => (
        <li key={tr.id}>
          <Link to={`/tracks/${tr.id}`} className="track-row">
            <span className="track-row__main">
              <strong>{tr.title ?? t("track.untitled")}</strong>
              <span className="muted">
                {formatDate(tr.started_at ?? tr.created_at)}
                {tr.category && ` · ${categoryLabel(tr.category)}`}
              </span>
            </span>
            {tr.status === "draft" || tr.status === "published" ? (
              <span className="track-row__stats">
                <span>{formatKm(tr.distance_m)} км</span>
                <span className="muted">
                  {formatDuration(tr.total_time_s)} · {formatPace(tr.avg_pace_s_per_km)}
                </span>
              </span>
            ) : null}
            {tr.new_attempts > 0 && (
              <span className="status-pill status-pill--fresh">
                {t("profile.freshAttempts", { count: tr.new_attempts })}
              </span>
            )}
            {showStatus && (
              <span className={`status-pill status-pill--${tr.status}`}>
                {tr.status === "published"
                  ? t(`track.visibility.${tr.visibility}`)
                  : t(`track.status.${tr.status}`)}
              </span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  );
}
