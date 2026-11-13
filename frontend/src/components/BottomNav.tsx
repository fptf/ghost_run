import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";

import { useAuth } from "../auth/useAuth";
import { useMe } from "../auth/useMe";

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path
        d={d}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Нижняя панель на телефоне (по макету Main): Карта, Рейтинги, Профиль. */
export function BottomNav() {
  const { t } = useTranslation();
  const { status } = useAuth();
  const me = useMe();
  const fresh = status === "authenticated" ? (me.data?.new_attempts ?? 0) : 0;
  return (
    <nav className="bottom-nav" aria-label={t("nav.main")}>
      <NavLink to="/" end className="bottom-nav__item">
        <Icon d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Zm0 0v14m6-12v14" />
        {t("nav.map")}
      </NavLink>
      <NavLink to="/ratings" className="bottom-nav__item">
        <Icon d="M8 21h8m-4-4v4M7 4h10v5a5 5 0 0 1-10 0V4Zm10 2h3a3 3 0 0 1-3 4M7 6H4a3 3 0 0 0 3 4" />
        {t("nav.ratings")}
      </NavLink>
      <NavLink to={status === "authenticated" ? "/me" : "/login"} className="bottom-nav__item">
        <span className="nav-icon">
          <Icon d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0" />
          {fresh > 0 && (
            <span
              className="nav-badge"
              aria-label={t("profile.newAttemptsBadge", { count: fresh })}
            >
              {fresh}
            </span>
          )}
        </span>
        {t("nav.profile")}
      </NavLink>
    </nav>
  );
}
