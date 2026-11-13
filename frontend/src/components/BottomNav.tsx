import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";

import { useAuth } from "../auth/useAuth";

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

/** Нижняя панель на телефоне (по макету Main). «Рейтинги» появятся в add-ratings. */
export function BottomNav() {
  const { t } = useTranslation();
  const { status } = useAuth();
  return (
    <nav className="bottom-nav" aria-label={t("nav.main")}>
      <NavLink to="/" end className="bottom-nav__item">
        <Icon d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Zm0 0v14m6-12v14" />
        {t("nav.map")}
      </NavLink>
      <NavLink to={status === "authenticated" ? "/me" : "/login"} className="bottom-nav__item">
        <Icon d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0" />
        {t("nav.profile")}
      </NavLink>
    </nav>
  );
}
