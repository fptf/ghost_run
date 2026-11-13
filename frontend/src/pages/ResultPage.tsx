import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { api } from "../api/client";
import type { Schemas } from "../api/client";
import { Avatar } from "../components/Avatar";
import { BackButton } from "../components/BackButton";
import { formatDiff, formatDuration } from "../lib/format";

type Row = Schemas["GroupRow"];

/** Строки вокруг бегуна: как в макете — вы и ближайшие соседи, автор маршрута всегда виден. */
function neighbours(rows: Row[]): Row[] {
  const i = rows.findIndex((r) => r.is_viewer);
  if (i < 0) return rows.slice(0, 3);
  const window = rows.slice(Math.max(0, i - 1), i + 3);
  const author = rows.find((r) => r.is_root);
  const shown = author && !window.includes(author) ? [...window, author] : window;
  return shown.sort((a, b) => a.place - b.place);
}

export function ShareButton({ path, text }: { path: string; text: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  async function share() {
    const url = `${window.location.origin}${path}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: text, text, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      // пользователь закрыл меню «Поделиться» — ничего не делаем
    }
  }
  return (
    <button type="button" className="btn btn--secondary" onClick={() => void share()}>
      {copied ? t("result.copied") : t("result.share")}
    </button>
  );
}

/** Экран результата попытки (макеты ResultWin, ResultSlower). */
export function ResultPage() {
  const { trackId = "" } = useParams();
  const { t } = useTranslation();
  const result = useQuery({
    queryKey: ["result", trackId],
    retry: false,
    queryFn: async () => {
      const { data, error } = await api.GET("/tracks/{track_id}/result", {
        params: { path: { track_id: trackId } },
      });
      if (error || !data) throw new Error("no result");
      return data;
    },
  });

  if (result.isPending) {
    return (
      <main className="page">
        <p className="muted">{t("common.loading")}</p>
      </main>
    );
  }
  if (result.isError || !result.data) {
    return (
      <main className="page page--narrow">
        <div className="card">
          <h1>{t("result.none")}</h1>
          <Link to={`/tracks/${trackId}`} className="btn btn--secondary">
            {t("result.toTrack")}
          </Link>
        </div>
      </main>
    );
  }

  const r = result.data;
  const won = r.outcome === "beat";
  const routeTitle = r.route.title ?? t("track.untitled");
  const authorName = r.route.author.name;
  const vs = t("result.versus", {
    mine: formatDuration(r.result_time_s),
    theirs: formatDuration(r.root_time_s),
  });
  const shareText = won
    ? t("result.shareWin", { route: routeTitle, diff: formatDiff(r.diff_s) })
    : t("result.shareRun", { route: routeTitle, time: formatDuration(r.result_time_s) });

  return (
    <main className="page page--narrow">
      <div className="page-head">
        <BackButton fallback={`/tracks/${trackId}`} />
        <h1 className="page-head__title">{t("result.title")}</h1>
      </div>

      <section className={`result-hero result-hero--${won ? "win" : "plain"}`}>
        {won ? (
          r.achievements.map((a) => (
            <span key={a.code} className="achievement-pill">
              <span aria-hidden>⚡</span> {t("result.achievement", { title: a.title })}
            </span>
          ))
        ) : (
          <span className="result-hero__label">{t("result.counted")}</span>
        )}
        <strong className="result-hero__diff">
          {r.outcome === "equal"
            ? t("result.equal")
            : `${r.diff_s < 0 ? "−" : "+"}${formatDiff(r.diff_s)}`}
        </strong>
        {r.outcome === "slower" && <span className="result-hero__sub">{t("result.missing")}</span>}
        <span className="result-hero__vs">
          {won ? t("result.versusAuthor", { vs, author: authorName }) : vs}
        </span>
        <Link to={`/tracks/${r.route.id}`} className="result-hero__route">
          {t("result.onRoute", { route: routeTitle })}
        </Link>
        {r.by_author && <span className="result-hero__sub">{t("match.ownRoute")}</span>}
      </section>

      <section className="card">
        <p className="row-between">
          <strong>{t("result.place", { place: r.place, count: r.runners })}</strong>
        </p>
        <ol className="group-table">
          {neighbours(r.rows).map((row) => (
            <li key={row.track_id} className={`group-row${row.is_viewer ? " group-row--me" : ""}`}>
              <span className="group-row__place">{row.place}</span>
              <span className="group-row__who">
                <Avatar name={row.runner.name} url={row.runner.avatar_url} small />
                <span className="group-row__name">
                  <span>{row.is_viewer ? t("result.youNewPlace") : row.runner.name}</span>
                  {row.is_root && <span className="group-mark">{t("group.author")}</span>}
                </span>
              </span>
              <span className="group-row__time">{formatDuration(row.time_s)}</span>
              <span />
            </li>
          ))}
        </ol>
        {r.gap_to_best_s > 0 && (
          <p className="muted">
            {t("result.toBest", {
              gap: formatDiff(r.gap_to_best_s),
              best: formatDuration(r.best_time_s),
            })}
          </p>
        )}
        <div className="row">
          <ShareButton path={`/tracks/${trackId}`} text={shareText} />
          <Link to={`/tracks/${r.route.id}`} className="btn btn--ghost">
            {t("result.wholeGroup")}
          </Link>
        </div>
      </section>
    </main>
  );
}
