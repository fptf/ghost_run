import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router";

import { api } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { useMe } from "../auth/useMe";
import { ProfileView } from "../components/ProfileView";
import { TrackList } from "../components/TrackList";

const FEEDS = ["tracks", "attempts", "achievements"] as const;
type Feed = (typeof FEEDS)[number];

export function MyProfilePage() {
  const { t } = useTranslation();
  const me = useMe();
  const { signOut } = useAuth();
  const navigate = useNavigate();
  const flash = (useLocation().state as { flash?: string } | null)?.flash;
  const [feed, setFeed] = useState<Feed>("tracks");
  const tracks = useQuery({
    queryKey: ["my-tracks"],
    queryFn: async () => (await api.GET("/me/tracks")).data ?? [],
  });

  if (!me.data) {
    return (
      <main className="page">
        <p className="muted">{t("common.loading")}</p>
      </main>
    );
  }
  return (
    <main className="page">
      {flash === "saved" && (
        <p role="status" className="notice notice--ok">
          {t("settings.saved")}
        </p>
      )}
      <ProfileView
        profile={me.data}
        extraStats={
          <div className="stat stat--accent">
            <dt>{t("profile.newAttempts")}</dt>
            <dd>{me.data.new_attempts}</dd>
          </div>
        }
        actions={
          <div className="row">
            <Link to="/settings" className="btn btn--secondary btn--sm">
              {t("nav.settings")}
            </Link>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => void signOut().then(() => navigate("/", { replace: true }))}
            >
              {t("nav.signOut")}
            </button>
          </div>
        }
      />
      <section className="card">
        <div className="segmented" role="tablist">
          {FEEDS.map((f) => (
            <button
              key={f}
              role="tab"
              type="button"
              className="segmented__item"
              aria-selected={feed === f}
              onClick={() => setFeed(f)}
            >
              {t(`profile.feeds.${f}`)}
            </button>
          ))}
        </div>
        <div role="tabpanel">
          {feed === "tracks" ? (
            <TrackList tracks={tracks.data ?? []} empty={t("profile.empty.tracks")} showStatus />
          ) : (
            <div className="empty">{t(`profile.empty.${feed}`)}</div>
          )}
        </div>
      </section>
    </main>
  );
}
