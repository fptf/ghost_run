import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Avatar } from "../components/Avatar";
import { PaceChart } from "../components/PaceChart";
import { CATEGORY_LABELS, formatDate } from "../lib/format";
import type { TrackDetail } from "../tracks/api";
import { GroupTable } from "../tracks/GroupTable";
import { TrackMetrics } from "../tracks/TrackSummaryCard";
import { useGpxDownload } from "../tracks/useGpxDownload";

/** Карточка выбранного трека в панели главной (по макету DesktopCard). */
export function TrackCardPanel({ track, onBack }: { track: TrackDetail; onBack: () => void }) {
  const { t } = useTranslation();
  const download = useGpxDownload();
  return (
    <article className="card-panel" aria-label={track.title ?? t("track.untitled")}>
      <button type="button" className="link-btn" onClick={onBack}>
        ← {t("search.backToList")}
      </button>
      <h2 className="card-panel__title">{track.title ?? t("track.untitled")}</h2>
      <p className="muted author-line">
        <Link to={`/users/${track.author.id}`} className="author-link">
          <Avatar name={track.author.name} url={track.author.avatar_url} small />
          {track.author.name}
        </Link>
        <span>
          · {t("search.ranOn", { date: formatDate(track.started_at) })}
          {track.category && ` · ${CATEGORY_LABELS[track.category] ?? track.category}`}
        </span>
      </p>
      <TrackMetrics track={track} />
      <PaceChart splits={track.splits} />
      <p className="notice notice--info">{t("track.runItHint")}</p>
      <div className="row">
        <button
          type="button"
          className="btn btn--primary btn--sm"
          onClick={() => void download(track.id, track.title)}
        >
          {t("track.downloadGpx")}
        </button>
        <Link
          to={`/tracks/${track.id}/check`}
          className="btn btn--secondary btn--sm"
          title={t("search.opensPage")}
        >
          {t("check.button")} ↗
        </Link>
        <Link
          to={`/tracks/${track.id}`}
          className="btn btn--ghost btn--sm"
          title={t("search.opensPage")}
        >
          {t("search.openPage")} ↗
        </Link>
      </div>
      <p className="field__hint">{t("search.navHint")}</p>
      <GroupTable trackId={track.id} external />
    </article>
  );
}
