import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";

import { api } from "../api/client";
import { ProfileView } from "../components/ProfileView";
import { TrackList } from "../components/TrackList";

export function PublicProfilePage() {
  const { userId = "" } = useParams();
  const { t } = useTranslation();
  const profile = useQuery({
    queryKey: ["profile", userId],
    queryFn: async () => {
      const { data, error } = await api.GET("/users/{user_id}", {
        params: { path: { user_id: userId } },
      });
      if (error || !data) throw new Error("not found");
      return data;
    },
    retry: false,
  });
  const tracks = useQuery({
    queryKey: ["user-tracks", userId],
    queryFn: async () =>
      (await api.GET("/users/{user_id}/tracks", { params: { path: { user_id: userId } } })).data ??
      [],
    enabled: profile.isSuccess,
  });

  return (
    <main className="page">
      {profile.isPending && <p className="muted">{t("common.loading")}</p>}
      {profile.isError && (
        <div className="card">
          <h1>{t("profile.notFound")}</h1>
        </div>
      )}
      {profile.data && (
        <>
          <ProfileView profile={profile.data} />
          <section className="card">
            <h2 className="card__title">{t("profile.tracks")}</h2>
            <TrackList tracks={tracks.data ?? []} empty={t("profile.noPublicTracks")} />
          </section>
        </>
      )}
    </main>
  );
}
