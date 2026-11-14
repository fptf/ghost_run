import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { Schemas } from "../api/client";
import { CATEGORY_LABELS, formatDuration } from "../lib/format";
import { CATEGORIES } from "../search/params";
import { Avatar } from "./Avatar";

export function ProfileView({
  profile,
  extraStats,
  actions,
}: {
  profile: Schemas["PublicProfile"];
  extraStats?: ReactNode;
  actions?: ReactNode;
}) {
  const { t } = useTranslation();
  const km = (profile.stats.total_distance_m / 1000).toLocaleString("ru-RU", {
    maximumFractionDigits: 1,
  });
  const records = Object.keys(profile.stats.records ?? {});
  return (
    <>
      <section className="card">
        <div className="profile-head">
          <Avatar name={profile.name} url={profile.avatar_url} />
          <div className="profile-head__meta">
            <h1>{profile.name}</h1>
            {profile.city && <p className="muted">{profile.city}</p>}
          </div>
        </div>
        {profile.about && <p>{profile.about}</p>}
        <dl className="stats">
          <div className="stat">
            <dt>{t("profile.runs")}</dt>
            <dd>{profile.stats.runs}</dd>
          </div>
          <div className="stat">
            <dt>{t("profile.totalKm")}</dt>
            <dd>{km}</dd>
          </div>
          {extraStats}
        </dl>
        {actions}
      </section>
      <section className="card">
        <h2 className="card__title">{t("profile.records")}</h2>
        {records.length === 0 ? (
          <div className="empty">{t("profile.noRecords")}</div>
        ) : (
          <dl className="stats">
            {CATEGORIES.filter((c) => profile.stats.records?.[c] != null).map((c) => (
              <div key={c} className="stat">
                <dt>{CATEGORY_LABELS[c]}</dt>
                <dd>{formatDuration(profile.stats.records?.[c])}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>
    </>
  );
}
