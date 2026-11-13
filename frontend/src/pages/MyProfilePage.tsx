import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useMe } from "../auth/useMe";
import { ProfileView } from "../components/ProfileView";

const FEEDS = ["tracks", "attempts", "achievements"] as const;
type Feed = (typeof FEEDS)[number];

export function MyProfilePage() {
  const { t } = useTranslation();
  const me = useMe();
  const [feed, setFeed] = useState<Feed>("tracks");

  if (!me.data) return <p>{t("common.loading")}</p>;
  return (
    <main>
      <ProfileView profile={me.data} />
      <p>
        {t("profile.newAttempts")}: <strong>{me.data.new_attempts}</strong>
      </p>
      <Link to="/settings">{t("nav.settings")}</Link>
      <div role="tablist">
        {FEEDS.map((f) => (
          <button
            key={f}
            role="tab"
            aria-selected={feed === f}
            onClick={() => setFeed(f)}
            type="button"
          >
            {t(`profile.feeds.${f}`)}
          </button>
        ))}
      </div>
      <section role="tabpanel">
        <p>{t(`profile.empty.${feed}`)}</p>
      </section>
    </main>
  );
}
