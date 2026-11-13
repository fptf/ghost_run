import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useSearchParams } from "react-router";

import { api } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { GoogleButton } from "../auth/GoogleButton";
import { safeNext } from "../auth/next";

export function LoginPage() {
  const { t } = useTranslation();
  const { status, signIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");

  const config = useQuery({
    queryKey: ["auth-config"],
    queryFn: async () => {
      const { data, error } = await api.GET("/auth/config");
      if (error || !data) throw new Error("config failed");
      return data;
    },
  });

  const finish = useCallback(
    (token: string) => {
      signIn(token);
      navigate(next, { replace: true });
    },
    [signIn, navigate, next],
  );

  const onGoogle = useCallback(
    async (idToken: string) => {
      const { data } = await api.POST("/auth/google", { body: { id_token: idToken } });
      if (data) finish(data.access_token);
      else setError(t("login.failed"));
    },
    [finish, t],
  );

  async function onDevSubmit(e: FormEvent) {
    e.preventDefault();
    const { data } = await api.POST("/auth/dev-login", { body: { email, name } });
    if (data) finish(data.access_token);
    else setError(t("login.failed"));
  }

  if (status === "authenticated") return <Navigate to={next} replace />;

  return (
    <main>
      <h1>{t("login.title")}</h1>
      {config.data?.google_client_id ? (
        <GoogleButton clientId={config.data.google_client_id} onCredential={onGoogle} />
      ) : (
        config.data && <p>{t("login.googleNotConfigured")}</p>
      )}
      {config.data?.dev_login_enabled && (
        <form onSubmit={onDevSubmit} aria-label={t("login.devTitle")}>
          <h2>{t("login.devTitle")}</h2>
          <label>
            {t("login.email")}
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            {t("login.name")}
            <input required value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <button type="submit">{t("login.devSubmit")}</button>
        </form>
      )}
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
