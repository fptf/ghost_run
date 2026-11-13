import { useTranslation } from "react-i18next";

import type { Schemas } from "../api/client";

export function ProfileView({ profile }: { profile: Schemas["PublicProfile"] }) {
  const { t } = useTranslation();
  const km = (profile.stats.total_distance_m / 1000).toLocaleString("ru-RU", {
    maximumFractionDigits: 1,
  });
  return (
    <section>
      {profile.avatar_url && <img src={profile.avatar_url} alt="" width={64} height={64} />}
      <h1>{profile.name}</h1>
      {profile.city && <p>{profile.city}</p>}
      {profile.about && <p>{profile.about}</p>}
      <dl>
        <dt>{t("profile.runs")}</dt>
        <dd>{profile.stats.runs}</dd>
        <dt>{t("profile.totalKm")}</dt>
        <dd>{km}</dd>
      </dl>
      <h2>{t("profile.records")}</h2>
      {Object.keys(profile.stats.records ?? {}).length === 0 && <p>{t("profile.noRecords")}</p>}
    </section>
  );
}
