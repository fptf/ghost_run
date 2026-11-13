import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";

export function HomePage() {
  const { t } = useTranslation();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error } = await api.GET("/health");
      if (error || !data) throw new Error("health check failed");
      return data;
    },
    retry: false,
  });

  const status = health.isPending
    ? t("health.loading")
    : health.data?.status === "ok"
      ? t("health.ok")
      : t("health.error");

  return (
    <main>
      <h1>{t("app.title")}</h1>
      <p>{t("app.tagline")}</p>
      <p>
        {t("health.label")}: <span data-testid="health-status">{status}</span>
      </p>
    </main>
  );
}
