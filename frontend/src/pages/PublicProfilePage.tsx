import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";

import { api } from "../api/client";
import { ProfileView } from "../components/ProfileView";

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

  if (profile.isPending) return <p>{t("common.loading")}</p>;
  if (profile.isError) return <h1>{t("profile.notFound")}</h1>;
  return (
    <main>
      <ProfileView profile={profile.data} />
    </main>
  );
}
