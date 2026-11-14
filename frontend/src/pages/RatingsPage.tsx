import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";

import { api } from "../api/client";
import { Avatar } from "../components/Avatar";
import { CATEGORY_LABELS, formatDuration, formatKm, formatPace } from "../lib/format";
import { CATEGORIES, isCategory } from "../search/params";
import type { Category } from "../search/params";

/** Рейтинги популярных маршрутов по категориям дистанции (ФТ-27–28), период «всё время». */
export function RatingsPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const raw = params.get("category");
  const category: Category = isCategory(raw) ? raw : "5";

  const rating = useQuery({
    queryKey: ["ratings", category],
    queryFn: async () => {
      const { data, error } = await api.GET("/ratings", {
        params: { query: { category, limit: 50 } },
      });
      if (error || !data) throw new Error("ratings failed");
      return data;
    },
  });
  const items = rating.data ?? [];

  return (
    <main className="page">
      <div className="stack">
        <h1>{t("ratings.title")}</h1>
        <p className="muted">{t("ratings.subtitle")}</p>
      </div>
      <div className="segmented" role="tablist" aria-label={t("ratings.categories")}>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            type="button"
            role="tab"
            className="segmented__item"
            aria-selected={category === c}
            onClick={() => setParams({ category: c }, { replace: true })}
          >
            {c === "21+" ? c : CATEGORY_LABELS[c]}
          </button>
        ))}
      </div>
      <section className="card" role="tabpanel">
        {rating.isPending && <p className="muted">{t("common.loading")}</p>}
        {rating.data && items.length === 0 && <div className="empty">{t("ratings.empty")}</div>}
        <ol className="rating-list">
          {items.map((it) => (
            <li key={it.track_id}>
              <Link to={`/tracks/${it.track_id}`} className="rating-row">
                <span
                  className={`rating-row__place${it.place <= 3 ? " rating-row__place--top" : ""}`}
                >
                  {it.place}
                </span>
                <span className="rating-row__main">
                  <strong>{it.title ?? t("track.untitled")}</strong>
                  <span className="muted rating-row__author">
                    <Avatar name={it.author.name} url={it.author.avatar_url} small />
                    {it.author.name}
                  </span>
                  <span className="muted">
                    {formatKm(it.distance_m)} км · {formatDuration(it.total_time_s)} ·{" "}
                    {formatPace(it.avg_pace_s_per_km)} /км
                  </span>
                  <span className="rating-row__stats">
                    {t("ratings.runners", { count: it.runners })} ·{" "}
                    {t("ratings.downloads", { count: it.downloads })}
                  </span>
                </span>
                <strong className="rating-row__score" title={t("ratings.scoreTitle")}>
                  {Math.round(it.value)}
                </strong>
              </Link>
            </li>
          ))}
        </ol>
        <p className="field__hint">{t("ratings.formula")}</p>
      </section>
    </main>
  );
}
