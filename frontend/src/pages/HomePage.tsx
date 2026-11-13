import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

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

  const state = health.isPending ? "loading" : health.data?.status === "ok" ? "ok" : "error";

  return (
    <main className="page">
      <section className="hero">
        <svg className="hero__route" viewBox="0 0 400 240" preserveAspectRatio="none" aria-hidden>
          <path
            d="M-10 228 C60 214 90 240 150 224 S250 186 300 204 S370 230 420 196"
            fill="none"
            stroke="#fff"
            strokeWidth="9"
            strokeLinecap="round"
          />
          <path
            d="M-10 228 C60 214 90 240 150 224 S250 186 300 204 S370 230 420 196"
            fill="none"
            stroke="#C2410C"
            strokeWidth="4"
            strokeLinecap="round"
          />
        </svg>
        <h1 className="hero__title">{t("app.title")}</h1>
        <p className="hero__text">{t("app.tagline")}</p>
        <div className="row">
          <Link to="/upload" className="btn btn--primary">
            {t("nav.upload")}
          </Link>
        </div>
      </section>
      <p className="status">
        <span className={`status__dot status__dot--${state}`} aria-hidden />
        {t("health.label")}: <span data-testid="health-status">{t(`health.${state}`)}</span>
      </p>
    </main>
  );
}
