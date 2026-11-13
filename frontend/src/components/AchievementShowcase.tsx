import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { api } from "../api/client";

/** Витрина ачивок бегуна в профиле. */
export function AchievementShowcase({ userId }: { userId: string }) {
  const { t } = useTranslation();
  const showcase = useQuery({
    queryKey: ["achievements", userId],
    queryFn: async () =>
      (await api.GET("/users/{user_id}/achievements", { params: { path: { user_id: userId } } }))
        .data ?? [],
  });
  const entries = showcase.data ?? [];
  return (
    <section className="card">
      <h2 className="card__title">{t("profile.feeds.achievements")}</h2>
      {entries.length === 0 ? (
        <div className="empty">{t("profile.empty.achievements")}</div>
      ) : (
        entries.map((e) => (
          <div key={e.code} className="showcase">
            <div className="showcase__head">
              <span className="achievement-pill">
                <span aria-hidden>⚡</span> {e.title}
              </span>
              <strong>×{e.count}</strong>
            </div>
            <p className="muted">{e.description}</p>
            <ul className="showcase__list">
              {e.items.map((i) => (
                <li key={i.track_id}>
                  <Link to={`/tracks/${i.track_id}`}>{i.title ?? t("track.untitled")}</Link>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}
