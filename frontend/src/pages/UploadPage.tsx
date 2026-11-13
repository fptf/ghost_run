import { useTranslation } from "react-i18next";

/** Заглушка: экран загрузки появится в add-track-upload. */
export function UploadPage() {
  const { t } = useTranslation();
  return (
    <main className="page">
      <h1>{t("upload.title")}</h1>
      <div className="empty">{t("upload.soon")}</div>
    </main>
  );
}
