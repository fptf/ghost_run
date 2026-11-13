import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { useAuth } from "../auth/useAuth";

export function Header() {
  const { t } = useTranslation();
  const { status, signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <header>
      <Link to="/">{t("app.title")}</Link>
      <nav>
        <button type="button" onClick={() => navigate("/upload")}>
          {t("nav.upload")}
        </button>
        {status === "authenticated" ? (
          <>
            <Link to="/me">{t("nav.profile")}</Link>
            <button type="button" onClick={() => void signOut()}>
              {t("nav.signOut")}
            </button>
          </>
        ) : (
          status === "guest" && <Link to="/login">{t("nav.signIn")}</Link>
        )}
      </nav>
    </header>
  );
}
