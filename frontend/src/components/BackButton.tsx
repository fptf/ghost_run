import { useTranslation } from "react-i18next";

import { useBack } from "../lib/useBack";

export function BackButton({ fallback }: { fallback: string }) {
  const { t } = useTranslation();
  const back = useBack(fallback);
  return (
    <button type="button" className="icon-btn" aria-label={t("common.back")} onClick={back}>
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
        <path
          d="M15 5l-7 7 7 7"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
