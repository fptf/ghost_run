import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { useAuth } from "../auth/useAuth";
import { useMe } from "../auth/useMe";
import { Avatar } from "./Avatar";
import { LogoMark } from "./LogoMark";

export function Header() {
  const { t } = useTranslation();
  const { status } = useAuth();
  const me = useMe();
  const navigate = useNavigate();

  return (
    <header className="header">
      <Link to="/" className="logo">
        <LogoMark className="logo__mark" />
        {t("app.title")}
      </Link>
      <nav className="header__nav">
        <button
          type="button"
          className="btn btn--primary btn--sm"
          aria-label={t("nav.upload")}
          onClick={() => navigate("/upload")}
        >
          {t("nav.uploadShort")}
          <span className="btn__long">{t("nav.uploadTail")}</span>
        </button>
        {status === "authenticated" ? (
          <>
            <Link to="/me" className="btn btn--ghost btn--sm" aria-label={t("nav.profile")}>
              <Avatar name={me.data?.name ?? ""} url={me.data?.avatar_url} small />
            </Link>
          </>
        ) : (
          status === "guest" && (
            <Link to="/login" className="btn btn--secondary btn--sm">
              {t("nav.signIn")}
            </Link>
          )
        )}
      </nav>
    </header>
  );
}
