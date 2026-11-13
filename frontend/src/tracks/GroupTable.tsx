import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { Schemas } from "../api/client";
import { Avatar } from "../components/Avatar";
import { formatDuration, formatPace } from "../lib/format";
import { useGroup } from "./useGroup";

function Mark({ row }: { row: Schemas["GroupRow"] }) {
  const { t } = useTranslation();
  const parts: string[] = [];
  if (row.is_root) parts.push(t("group.author"));
  else if (row.is_author) parts.push(t("group.authorAgain"));
  if (row.beat) parts.push(t("group.beat"));
  if (row.runs > 1) parts.push(t("group.bestOf", { count: row.runs }));
  if (parts.length === 0) return null;
  return (
    <span className={`group-mark${row.beat ? " group-mark--beat" : ""}`}>{parts.join(" · ")}</span>
  );
}

/** Таблица группы маршрута (по макетам Card / DesktopCard): лучший результат каждого бегуна. */
export function GroupTable({ trackId, limit = 5 }: { trackId: string; limit?: number }) {
  const { t } = useTranslation();
  const group = useGroup(trackId);
  const [all, setAll] = useState(false);

  if (!group.data) return null;
  const { rows, runners } = group.data;
  const shown = all ? rows : rows.slice(0, limit);
  return (
    <section className="group" aria-label={t("track.group")}>
      <div className="row-between">
        <h3 className="card__title">{t("track.group")}</h3>
        <span className="muted">{t("search.runnersShort", { count: runners })}</span>
      </div>
      {runners <= 1 ? (
        <div className="empty">{t("search.onlyAuthor")}</div>
      ) : (
        <ol className="group-table">
          {shown.map((row) => (
            <li key={row.track_id} className={`group-row${row.is_viewer ? " group-row--me" : ""}`}>
              <span className="group-row__place">{row.place}</span>
              <span className="group-row__who">
                <Avatar name={row.runner.name} url={row.runner.avatar_url} small />
                <span className="group-row__name">
                  <Link to={`/tracks/${row.track_id}`}>
                    {row.is_viewer ? t("group.you") : row.runner.name}
                  </Link>
                  <Mark row={row} />
                </span>
              </span>
              <span className="group-row__time">{formatDuration(row.time_s)}</span>
              <span className="group-row__pace muted">{formatPace(row.pace_s_per_km)}</span>
            </li>
          ))}
        </ol>
      )}
      {rows.length > limit && (
        <button type="button" className="link-btn" onClick={() => setAll(!all)}>
          {all ? t("group.collapse") : t("group.showAll", { count: rows.length })}
        </button>
      )}
    </section>
  );
}
