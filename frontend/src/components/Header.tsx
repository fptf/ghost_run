import { useTranslation } from "react-i18next";
import { Link, NavLink, useNavigate } from "react-router";

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
      <nav className="header__links" aria-label={t("nav.main")}>
        <NavLink to="/" end className="header__link">
          {t("nav.map")}
        </NavLink>
      </nav>
      <nav className="header__nav">
        <button
          type="button"
          className="btn btn--primary btn--sm btn--nogap"
          aria-label={t("nav.upload")}
          onClick={() => navigate("/upload")}
        >
          {t("nav.uploadShort")}
          <span className="btn__long">&nbsp;{t("nav.uploadTail")}</span>
        </button>
        {status === "authenticated" ? (
          <>
            <Link to="/me" className="btn btn--ghost btn--sm" aria-label={t("nav.profile")}>
              <span className="nav-icon">
                <Avatar name={me.data?.name ?? ""} url={me.data?.avatar_url} small />
                {(me.data?.new_attempts ?? 0) > 0 && (
                  <span
                    className="nav-badge"
                    aria-label={t("profile.newAttemptsBadge", {
                      count: me.data?.new_attempts ?? 0,
                    })}
                  >
                    {me.data?.new_attempts}
                  </span>
                )}
              </span>
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
