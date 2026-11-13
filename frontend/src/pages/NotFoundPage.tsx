import { useTranslation } from "react-i18next";
import { Link } from "react-router";

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <main className="page page--narrow">
      <div className="card">
        <h1>{t("notFound.title")}</h1>
        <Link to="/" className="btn btn--secondary">
          {t("notFound.home")}
        </Link>
      </div>
    </main>
  );
}
